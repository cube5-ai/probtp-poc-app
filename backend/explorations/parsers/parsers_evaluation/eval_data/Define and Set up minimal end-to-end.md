# Define and Set up minimal end-to-end evaluation

Type: Development
Priority: Medium
Assignee: Jean-Baptiste RENAULT
Status: Done
Due: September 25, 2025
Project: Technical Requirements (https://www.notion.so/Technical-Requirements-2728a04d4edd80d0ba17c336850c3444?pvs=21)
Time Frame: September 25, 2025 8:45 AM (GMT+2) → 10:30 AM

This task focuses on implementing a minimal end-to-end evaluation system for our medical insurance policy comparison tool, which uses document parsing and LLM-based analysis.

## Description

As a AI engineer, I want to evaluate the accuracy and effectiveness of our insurance policy comparison system so that I can ensure it correctly extracts and compares key policy features from different insurance documents.

## Acceptance criteria

- Set up an evaluation pipeline that can measure the accuracy of document parsing for insurance policies
- Define metrics to evaluate the quality of LLM-based analysis (precision, recall, F1-score)
- Create a minimal test dataset of at least 3 ideally 10 diverse insurance policy documents with known features/details
- Implement automated comparison between system output and ground truth
- Ensure the evaluation can run end-to-end without manual intervention
- Document the evaluation methodology for future reference

---

## Evaluation Data Set

| Fichier | Catégorie 1 | Catégorie 2 | Catégorie 3 | Niveau | Valeur | Conditions |
| --- | --- | --- | --- | --- | --- | --- |
| #2 | Soins courants | Honoraires paramédicaux | Transport | S1 | 100% | `None` |
| #2 | Soins courants | Médicaments | Contraception prescrite, non remboursée par la S.S.  | S2 | `Null` | `None` |
| #2 |  Soins courants | Médicaments | Vaccins | S4 | Tous vaccins
60 € / an / benificiare | Vaccin prescrit ayant reçu une autorisation de mise sur le marché. Montant en
euros : plafond par an et par bénéficiaire |
| #2 |  Soins courants | Honoraires paramédicaux  | Auxiliaires médicaux, soins infirmiers  | S4 | 200% |  |
| #2 |  Soins courants | Honoraires
médicaux | Radiologie | S5 | 200 % **(Frais réels si OPTAM)** |  |
| #1 | Prévention | Vaccins |  | Option 1 | 6 % PMSS an / benificiare | non pris en charge par la Sécurité sociale,
prescrits par un médecin dans les conditions prévues par leur autorisation
de mise sur le marché |
| #1 | Prévention | Consultation chez un diététicien |  | Base obligatoire | 1,25 % PMSS |  prescrite par un médecin, dans la limite
d’une prise en charge durant la vie du contrat. Par enfant de moins de 12 ans. |
| #2 | Orthodontie | Orthodontie | prise en charge par la Sécurité sociale  | P6 | 500 % | Par semestre |
| #1 | Optique | Monture |  | Base obligatoire | 100€ | Dans le réseau optique Itelis |
| #1 | Optique | Autres postes optique | Les lentilles de contact correctrices prises en charge ou non par la Sécurité sociale | Base obligatoire | 200€/an/beneficiare | Nous garantissons au minimum : 100 % TM  |
| #2 | Optique | Lentilles | Lentilles non remboursées par la S.S.  | P4 | 150€ | Montant en euros : forfait par an et par bénéficiaire |
| #2 | Dentaire | Soins dentaires | Parodontologie non prise en charge
par la S.S. (/ an / bénéf.) (12)  | p3+ | 250 €  | Montant en euros : forfait par an et par bénéficiaire |
| #1 | Dentaire | Prothèses (Hors 100% Santé) | à tarifs libre (3) (y compris Inlay Onlay)  | Option 1 | 500 % BR-MR |  |
| #1 | Soins courants | Médicaments | homéopathiques non pris en charge par la Sécurité sociale et prescrits par
un médecin | base
obligatoire | 60 € | Par année civile et par bénéficiaire |
| #1 | Dentaire | Implantologie dentaire non prise en charge par la Sécurité sociale | Pose de l’implant (phase opératoire)  | base
obligatoire | 616 € | Dans la limite, par année civile et par bénéficiaire, de : 3 acte(s)  |
| #1 | Soins courants | Médecines non conventionnelles | Forfait actes thérapeutiques pour les actes cités ci-contre, Acupuncture, Chiropraxie, Diététique, Ostéopathie,
Pédicurie-podologie,
Psychologie,
Psychomotricité,
Tabacologie | Option 1 | 55 € | par séance, Dans la limite, par année civile et par bénéficiaire, de 3 seances |
| #2 | Dentaire | Soins dentaires | Inlay/onlay (par acte) | P5 | 250 % |  |
| #2 | Prestations | Cures thermales |  | P1 | 65 %  |  |
| #2 | Aides auditives | Prothese auditives | Pour les beneficiares de > 20 ans | P2 | 1000€ | Si partenaire audioprothésiste
Sévéane  |
| #2 | Aides auditives | Prothese auditives | Pour les beneficiares  de > 20 ans | P3+ | 950€ |  Si non partenaire audioprothésiste
Sévéane  |
| #2 | Aides auditives | Prothese auditives | Pour les beneficiares de  20 ans ou moins | P3+ | 1400€ |  Si non partenaire audioprothésiste
Sévéane  |

Question :

- “Vaccins non remboursés par la S.S. (1)” faut il comprendre que les vaccins sont pris en charge a 100% et tombe dans la catégorie “Pharmacie remboursée par la S.S.” ?

- Comment modeliser cela, soit juste un niveau “Prothese dentaire” puis une liste de valeurs conditionnees ?
    
    ![image.png](Define%20and%20Set%20up%20minimal%20end-to-end%20evaluation%202768a04d4edd8084a3e6ef74cf3aeee9/image.png)
    

- Plus generalement, souhaite-t-on de la purete dans les dimensions (Dimension - Type de Garanties) ou de la flexibilite en collant plus a ce qui est fourni ?
    - Je pencherais plus pour la flexibilite, meme si on perds peut etre de la generalite on aborde le probleme en collant a la facon dont le metier l’approche, en restant proche de la perspective initiale on peut plus facilement communique le résultat de l’analyse a un utilisateur du metier.