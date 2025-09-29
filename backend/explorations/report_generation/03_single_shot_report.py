"""
Single-shot report generation from parsed content blocks.

This script reads content blocks from the database (parsed in step 02),
reconstructs the documents in order, and uses Gemini to generate a comprehensive
comparative report of insurance policies in French.
"""

import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from langfuse import Langfuse, observe
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.content_block_db import ContentBlockDB
from app.models.file import File
from app.models.project import Project
from app.services.content_block_service import ContentBlockService

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize settings and model name globally
settings = get_settings()
# model_name = "gemini-2.5-flash-preview-09-2025"  # Using latest model for better performance
model_name = "gemini-2.5-pro"  # Using latest model for better performance

# Initialize Langfuse
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# Set up Google GenAI instrumentation for Langfuse
GoogleGenAIInstrumentor().instrument()


class GeminiClientManager:
    """Context manager for proper Gemini client lifecycle management"""

    def __init__(self):
        self.client = None

    def __enter__(self):
        GoogleGenAIInstrumentor().instrument()

        self.client = genai.Client(
            vertexai=True,
            project="probtp-poc-prod",
            location="global",
        )
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            # Properly close the client if it has a close method
            if hasattr(self.client, "close"):
                try:
                    self.client.close()
                except Exception as e:
                    logger.warning(f"Error closing Gemini client: {e}")
            self.client = None


@observe()
def get_test_project() -> Project | None:
    """Get the test project created by setup script"""
    db = SessionLocal()
    try:
        project = (
            db.query(Project).filter(Project.name == "Report Generation Test").first()
        )
        if not project:
            logger.error(
                "Test project not found. Please run 00_config_and_setup.py first."
            )
            return None
        return project
    finally:
        db.close()


@observe()
def get_parsed_files(project_id: str) -> list[File]:
    """Get all files with parsed content blocks"""
    db = SessionLocal()
    try:
        # Get files that have content blocks
        files = (
            db.query(File)
            .filter(File.project_id == project_id, File.status == "ready")
            .all()
        )

        # Filter to only files with content blocks
        parsed_files = []
        for file in files:
            block_count = (
                db.query(ContentBlockDB)
                .filter(ContentBlockDB.file_id == file.id)
                .count()
            )

            if block_count > 0:
                parsed_files.append(file)
                logger.info(
                    f"Found parsed file: {file.original_name} with {block_count} blocks"
                )

        return parsed_files
    finally:
        db.close()


@observe()
def reconstruct_document(file_id: str) -> dict[str, Any] | None:
    """Reconstruct a document from its content blocks in database"""
    db = SessionLocal()
    try:
        # Get file info
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.error(f"File {file_id} not found")
            return None

        # Get all content blocks ordered by page and position
        blocks = ContentBlockService.get_content_blocks_for_file(db, uuid.UUID(file_id))

        # Group blocks by page
        pages: dict[int, list[dict[str, Any]]] = {}
        for block in blocks:
            page_num = block.page_number or 0
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(
                {
                    "type": block.block_type,
                    "content": block.content,
                    "confidence": block.confidence_score,
                    "position": block.position,
                }
            )

        # Sort pages and their blocks
        sorted_pages: list[dict[str, Any]] = []
        for page_num in sorted(pages.keys()):
            page_blocks = sorted(pages[page_num], key=lambda x: x.get("position", 0))
            sorted_pages.append({"page_number": page_num, "blocks": page_blocks})

        return {
            "file_id": str(file.id),
            "file_name": file.original_name,
            "total_blocks": len(blocks),
            "total_pages": len(sorted_pages),
            "pages": sorted_pages,
            "block_types": list({b.block_type for b in blocks}),
        }
    finally:
        db.close()


def extract_text_from_document(document: dict) -> str:
    """Extract all text content from a reconstructed document"""
    text_parts = []

    for page in document["pages"]:
        page_text = []
        for block in page["blocks"]:
            if block["type"] in ["text", "heading", "list", "table"] and block.get(
                "content"
            ):
                page_text.append(block["content"])

        if page_text:
            text_parts.append(f"--- Page {page['page_number'] + 1} ---")
            text_parts.extend(page_text)

    return "\n".join(text_parts)


def create_comparative_prompt(documents: list) -> str:
    """Create a prompt for generating a comparative report in French"""

    # Build document context
    doc_contexts = []
    for i, doc in enumerate(documents, 1):
        text_content = extract_text_from_document(doc)
        print(text_content)
        doc_contexts.append(f"""
=== Document {i}: {doc["file_name"]} ===
Nombre de pages: {doc["total_pages"]}
Nombre de blocs: {doc["total_blocks"]}

Contenu:
{text_content}
""")

    prompt = f"""## Contexte
Vous êtes un expert en analyse de contrats de mutuelle santé. Vous allez recevoir des extraits de documents provenant de contrats de mutuelle qui ont été extraits automatiquement de PDF complexes. Ces textes peuvent contenir du bruit (caractères mal reconnus, mise en forme perturbée, informations fragmentées).

## Objectif
Produire un document de synthèse alignant les garanties des différents contrats pour permettre une comparaison rapide et efficace, sans avoir besoin d'ouvrir les documents originaux côte à côte.

## Instructions détaillées

### 1. Extraction et identification des contrats
- **Identifier chaque contrat** présent dans les documents :
  - Nom commercial du contrat
  - Organisme assureur (mutuelle/compagnie)
  - Numéro de contrat si disponible
  - Date d'effet ou version du contrat
- **Identifier les niveaux de garantie** (formules/options) :
  - Exemples courants : Base, Option 1, Option 2, Formule Eco, Confort, Premium, etc.
  - Noter que certaines garanties peuvent avoir des niveaux différents selon les catégories

### 2. Catégorisation des garanties
Organiser les garanties selon les catégories standards de soins :
- **Hospitalisation** (frais de séjour, honoraires, chambre particulière, etc.)
- **Soins courants** (consultations, médicaments, analyses, radiologie, etc.)
- **Optique** (verres, montures, lentilles, chirurgie réfractive)
- **Dentaire** (soins, prothèses, orthodontie, implants)
- **Aides auditives** (appareillage, piles, entretien)
- **Médecines douces** (ostéopathie, acupuncture, psychologie, etc.)
- **Prévention** (vaccins, bilans de santé, sevrage tabagique)
- **Autres garanties** (cure thermale, transport, assistance, etc.)

### 3. Création des tableaux comparatifs alignés

Pour **chaque catégorie de soins**, créer un tableau avec :

**Structure des colonnes :**
| Garantie | Garantie sous section | [Contrat 1 - Niveau 1] | [Contrat 1 - Niveau 2] | ... | [Contrat 2 - Niveau 1] | [Contrat 2 - Niveau 2] | ... |

**Contenu des cellules :**
- Montants de remboursement (en euros ou en % BR/PMSS)
- Conditions spécifiques (délais de carence, plafonds annuels)
- Limitations éventuelles
- Utiliser "-" ou "Non couvert" si la garantie n'existe pas
- Conserver la formulation exacte des montants trouvés dans les documents

### 4. Gestion des données bruitées
- **Signaler les ambiguïtés** : Si une information est peu claire ou incomplète, l'indiquer avec [?]
- **Données manquantes** : Utiliser "N.D." (non disponible) si l'information devrait exister mais n'est pas trouvée
- **Incohérences** : Si des valeurs semblent incorrectes (ex: montants aberrants), les reporter telles quelles mais ajouter une note

### 5. Format de sortie
```markdown
# Comparatif des garanties de mutuelle

## 1. Identification des contrats

### Contrat A
- **Assureur** : [Nom]
- **Nom du contrat** : [Nom commercial]
- **Niveaux disponibles** : [Liste des formules/options]

### Contrat B
- **Assureur** : [Nom]
- **Nom du contrat** : [Nom commercial]
- **Niveaux disponibles** : [Liste des formules/options]

## 2. Tableaux comparatifs par catégorie

### SOINS COURANTS

| Garantie | Garantie sous section | [Contrat A - Base] | [Contrat A - Option 1] | ... | [Contrat B - Confort] |
|----------|-------------------|------------------------|-------------------|----------------------|
| Honoraires médicaux | Consultations et visites (généralistes et spécialistes)  | ... | ... | ... | ... |
| Honoraires médicaux | Radiologie | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |
| Médicaments | Pharmacie remboursée par la S.S. | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |
....

### OPTIQUE

[Tableau similaire]

### DENTAIRE

[Tableau similaire]

[Continuer pour chaque catégorie...]

## Notes sur la qualité des données
[Si nécessaire, lister ici les problèmes rencontrés dans l'extraction]
```
## Consignes finales
- Prioriser la lisibilité et la comparabilité des informations
- Être exhaustif : inclure toutes les garanties trouvées
- Maintenir une cohérence dans la présentation des montants
- Ne pas interpréter ou calculer : reporter les informations telles qu'elles apparaissent
- Utiliser le français pour tous les textes
- Produire directement le document de synthèse sans commentaire introductif

{"".join(doc_contexts)}
"""

    return prompt


@observe()
def generate_report(documents: list) -> str | None:
    """Generate a comparative report using Gemini"""

    logger.info(f"Generating report for {len(documents)} documents...")

    # Create the prompt
    prompt = create_comparative_prompt(documents)

    try:
        # Use context manager for proper client lifecycle
        with GeminiClientManager() as client:
            # Generate report with Gemini
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": 0.1,  # Lower temperature for more factual output
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 16000,
                    "response_mime_type": "text/plain",
                },
            )

            if response and response.text:
                return response.text
            else:
                logger.error("No response received from Gemini")
                return None

    except Exception as e:
        logger.error(f"Error generating report with Gemini: {e}")
        return None


def save_report(report_content: str, output_dir: str = "reports") -> str:
    """Save the generated report to a file"""

    # Create output directory if it doesn't exist
    reports_dir = os.path.join(os.path.dirname(__file__), output_dir)
    os.makedirs(reports_dir, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"comparative_report_{timestamp}.md"
    filepath = os.path.join(reports_dir, filename)

    # Save the report
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info(f"Report saved to: {filepath}")
    return filepath


@observe()
def main():
    """Main execution function"""
    print("=" * 60)
    print("📊 SINGLE-SHOT REPORT GENERATION FROM PARSED DOCUMENTS")
    print("=" * 60)
    print()

    # Get test project
    project = get_test_project()
    if not project:
        return

    print(f"Using project: {project.name} (ID: {project.id})")
    print()

    # Get parsed files
    parsed_files = get_parsed_files(str(project.id))

    if not parsed_files:
        print("❌ No parsed files found in the database")
        print("Please run 02_read_and_parse_file.py first to parse documents")
        return

    print(f"Found {len(parsed_files)} parsed files:")
    for file in parsed_files:
        print(f"  - {file.original_name}")
    print()

    # Reconstruct documents from database
    print("📄 Reconstructing documents from content blocks...")
    documents = []

    for file in parsed_files:
        doc = reconstruct_document(str(file.id))
        if doc:
            documents.append(doc)
            print(f"  ✅ Reconstructed: {doc['file_name']}")
            print(f"     Pages: {doc['total_pages']}, Blocks: {doc['total_blocks']}")
            print(f"     Block types: {', '.join(doc['block_types'])}")

    if not documents:
        print("❌ Failed to reconstruct any documents")
        return

    print()
    print("🤖 Generating comparative report with Gemini...")
    print("  This may take a moment...")

    # Update current trace with comprehensive metadata
    langfuse.update_current_trace(
        input={
            "project_id": str(project.id),
            "project_name": project.name,
            "documents_count": len(documents),
            "document_files": [doc["file_name"] for doc in documents],
            "total_pages": sum(doc["total_pages"] for doc in documents),
            "total_blocks": sum(doc["total_blocks"] for doc in documents),
            "model_name": model_name,
        },
        user_id="report-generation-user",
        session_id=f"report-session-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        tags=["report-generation", "insurance-analysis", "comparative-report"],
        metadata={
            "environment": settings.environment,
            "script_version": "1.0.0",
            "block_types_found": list(
                {block_type for doc in documents for block_type in doc["block_types"]}
            ),
            "execution_timestamp": datetime.now().isoformat(),
        },
        version="1.0.0",
    )

    # Generate the report
    report = generate_report(documents)

    if report:
        print("  ✅ Report generated successfully!")
        print()

        # Save the report
        filepath = save_report(report)

        # Display a preview
        print("📋 Report Preview (first 1000 characters):")
        print("-" * 60)
        print(report[:1000])
        if len(report) > 1000:
            print("...")
        print("-" * 60)
        print()

        print(f"✅ Full report saved to: {filepath}")
        print(f"   Report length: {len(report)} characters")

        # Basic statistics
        lines = report.split("\n")
        tables = sum(1 for line in lines if "|" in line and "-" in line)
        print(f"   Lines: {len(lines)}")
        print(f"   Potential tables: {tables // 3}")  # Rough estimate

        # Update trace with final results
        langfuse.update_current_trace(
            output={
                "report_generated": True,
                "report_length": len(report),
                "report_lines": len(lines),
                "estimated_tables": tables // 3,
                "output_file": filepath,
            }
        )

    else:
        print("❌ Failed to generate report")
        print("Check the logs for more details")

        # Update trace with failure information
        langfuse.update_current_trace(
            output={"report_generated": False, "error": "Report generation failed"}
        )

    # Ensure all events are sent to Langfuse before script completion
    langfuse.flush()


if __name__ == "__main__":
    main()
