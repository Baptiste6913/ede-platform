# CLAUDE.md — Projet Sites Web

> Ce fichier est lu automatiquement par Claude Code à chaque session.
> Il constitue la mémoire et le cadre de travail du projet.

---

## DOSSIER DE TRAVAIL

```
C:\Users\bapti\Downloads\Site web\
```

Tous les projets de sites web sont créés dans des sous-dossiers ici.

---

## ⚠️ PROCÉDURE OBLIGATOIRE AVANT DE CODER

**Tu ne touches PAS au code avant d'avoir complété ces étapes dans l'ordre :**

### Étape 1 — Lire les fichiers de contexte du projet
Si un sous-dossier projet contient ces fichiers, lis-les TOUS avant de commencer :
1. `DESIGN-SYSTEM.md` — Tokens, palette, typo, spacing, shadows, motion, icônes
2. `EXPERIENCE-ENGINE.md` — Directive créative : animations 3D, scroll triggers, parallax, transitions, micro-interactions
3. `COPY-GUIDE.md` — Ton éditorial, mots à utiliser/éviter, hiérarchie CTA
4. `REFERENCES.md` — Sites d'inspiration et anti-références
5. `PROMPT.md` — Brief créatif détaillé du projet (si présent)

### Étape 2 — Charger les skills pertinentes
Avant toute tâche frontend, lis les SKILL.md de ces skills installées :
- `/ui-ux-pro-max` — Design system avancé, styles premium, patterns UI
- `/frontend-design` — Skill officielle Anthropic anti-AI-slop
- `/bencium-innovative-ux-designer` — 28K caractères de guidelines UX
- `/bencium-controlled-ux-designer` — Cohérence multi-pages
- `/typography` — Règles typographiques professionnelles
- `/design-audit` — Audit design 17 règles, score /100
- `/distinctive-frontend` — Choix esthétiques audacieux

### Étape 3 — Vérifier les outils disponibles
Tu as accès à ces outils. Utilise-les :
- **MCP `magic` (21st.dev)** — Génère des composants UI premium. Utilise-le pour les éléments complexes (carousels, cards, navbars)
- **`framer-motion`** (npm) — Installé globalement. Pour les projets React, utilise-le directement. Pour le vanilla JS, reproduis ses easings et ses patterns d'animation
- **Google Fonts** — Charge toujours via `<link>` dans le `<head>`. Polices par défaut du design system : Plus Jakarta Sans, DM Sans, DM Mono

---

## ARSENAL COMPLET

### Skills Claude Code installées
```
~/.claude/skills/
├── ui-ux-pro-max/              ← Design system avancé (nextlevelbuilder)
├── frontend-design/            ← Anti-AI-slop officiel Anthropic
├── bencium-innovative-ux/      ← UX designer créatif (28K chars)
├── bencium-controlled-ux/      ← UX designer cohérent
├── typography/                 ← Règles typo pro (bencium)
├── design-audit/               ← Audit 17 règles /100 (bencium)
└── distinctive-frontend/       ← Choix esthétiques audacieux (Koomook)
```

### MCP Servers configurés
```
magic (21st.dev) — Composants UI premium
  → Scope: user
  → Commande: npx -y @21st-dev/magic@latest
```

### Packages NPM installés
```
framer-motion — Animations et transitions React
```

### Fichiers de contexte (par projet)
```
DESIGN-SYSTEM.md     → Tokens visuels complets
EXPERIENCE-ENGINE.md → Directive créative animations/3D/scroll
COPY-GUIDE.md        → Ton éditorial et copywriting
REFERENCES.md        → Inspiration visuelle ciblée
PROMPT.md            → Brief créatif du projet
```

---

## STANDARDS DE QUALITÉ

### Chaque site web doit :
- Ressembler à un **Awwwards Site of the Day**, pas un template Bootstrap
- Avoir des **animations uniques par section** (jamais le même reveal deux fois)
- Utiliser des **transforms 3D** (perspective, rotateX/Y, translateZ)
- Implémenter du **parallax multicouche** (minimum 3 couches de profondeur)
- Avoir des **micro-interactions** sur chaque élément interactif (cards 3D tilt, boutons magnétiques, shimmer CTA)
- Supporter **`prefers-reduced-motion`** pour l'accessibilité
- Tourner à **60fps** (uniquement `transform` et `opacity` pour les animations)
- Être **responsive** (mobile-first, breakpoints : 640, 768, 1024, 1280px)

### Ce qui est INTERDIT :
- Templates génériques, layouts prévisibles, Inter/Roboto/Arial
- Fade-in simple sans transform
- Même animation sur deux sections consécutives
- Cards sans hover 3D
- Boutons sans micro-interaction
- Fond uni sans profondeur (pas de blob, pas de gradient mesh)
- Grilles qui apparaissent d'un coup (toujours stagger)
- Texte qui apparaît en bloc (toujours split words/lines)

---

## STRUCTURE TYPE D'UN PROJET

```
Projet/
├── index.html
├── [autres-pages].html
├── css/
│   ├── globals.css        (variables, reset, typo, keyframes)
│   ├── components.css     (navbar, footer, buttons, cards)
│   └── pages/
│       └── [page].css
├── js/
│   ├── main.js            (observers, parallax engine, smooth scroll)
│   ├── animations.js      (scroll reveals, counters, split text)
│   ├── carousel.js        (drag/swipe carousel)
│   └── navbar.js          (sticky, mobile menu, active state)
├── DESIGN-SYSTEM.md
├── EXPERIENCE-ENGINE.md
├── COPY-GUIDE.md
├── REFERENCES.md
└── PROMPT.md
```

---

## PROJETS EN COURS

### Rhinovate (rhinovate.ai)
- **Dossier** : `C:\Users\bapti\Downloads\Site web\Rhinovate\`
- **Type** : Site complet multi-pages (5 pages)
- **Vibe** : Medical premium + tech moderne, thème CLAIR
- **Pages** : Home, Product, Pricing, About, Contact
- **Brief complet** : voir `PROMPT.md` dans le dossier

---

## RAPPEL FINAL

Tu n'es pas un générateur de code. Tu es un **directeur artistique digital** qui code. Chaque pixel, chaque animation, chaque transition doit être intentionnelle. Si un visiteur ne dit pas "wow" au moins une fois en scrollant, tu as échoué.

Lis les fichiers. Charge les skills. Utilise les outils. Puis crée quelque chose d'exceptionnel.
