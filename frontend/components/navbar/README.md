# Navbar Component

Horizontal navigation bar with logo, breadcrumbs, and user menu.

## Usage

```tsx
import { Navbar } from "@/components/navbar";

// Simple breadcrumb (current page only)
<Navbar breadcrumbs={[{ label: "Home" }]} />

// Multiple breadcrumbs with links
<Navbar
  breadcrumbs={[
    { label: "Home", href: "/" },
    { label: "Projects", href: "/projects" },
    { label: "Project Details" }
  ]}
/>
```

## Components

### Navbar

- **Logo**: ProBTP logo on the left
- **Breadcrumbs**: Dynamic breadcrumb navigation in the center
- **User Menu**: User dropdown on the right

### UserMenu

- Displays user email
- Profile link
- Settings link
- Sign out button

## Props

### Navbar Props

```typescript
interface BreadcrumbItemType {
  label: string; // Text to display
  href?: string; // Optional link (last item is always non-clickable)
}

interface NavbarProps {
  breadcrumbs?: BreadcrumbItemType[]; // Optional array of breadcrumb items
}
```
