# ClimaZone — Accès à distance pour les clients (Cloudflare Tunnel)

Objectif : chaque client accède à son automate depuis **n'importe où**, via une
**simple adresse web** (ex. `maison-dupont.votredomaine.fr`), en se connectant
avec **ses propres identifiants** ClimaZone. Aucune app à installer, aucune
configuration de box, connexion **chiffrée (HTTPS)**.

---

## Étape 1 — Prendre un nom de domaine (une fois)
- Achetez un domaine (~8-12 €/an). Recommandé : **Cloudflare Registrar**
  (dash.cloudflare.com → *Domain Registration* → *Register Domains*), OVH, Gandi…
- Si acheté ailleurs, ajoutez-le à un **compte Cloudflare gratuit**
  (dash.cloudflare.com → *Add a site*).

## Étape 2 — Créer un tunnel (par automate)
1. Sur **dash.cloudflare.com** → **Zero Trust** → **Networks → Tunnels**.
2. **Create a tunnel** → type **Cloudflared** → nommez-le (ex. `maison-dupont`).
3. Cloudflare affiche une commande contenant un **token** (`eyJh...` très long).
   **Copiez uniquement ce token.**
4. **Public Hostname** → **Add a public hostname** :
   - *Subdomain* : `maison-dupont` (ou le nom du client)
   - *Domain* : votre domaine
   - *Service* : **HTTP** → `localhost:80`
   - Enregistrez.

## Étape 3 — Activer sur l'automate
Dans `~/zoneclimate/.env`, ajoutez la ligne (avec votre token) :
```
CLOUDFLARE_TUNNEL_TOKEN=eyJh...votre_token...
```
Puis démarrez le tunnel :
```bash
cd ~/zoneclimate
sudo docker compose -f docker-compose.pi.yml --profile remote up -d
```

## Étape 4 — Utilisation
Le client ouvre `https://maison-dupont.votredomaine.fr` depuis **n'importe où**
→ page de connexion ClimaZone → il entre **ses identifiants**. ✅

---

### Pour plusieurs clients
Un **tunnel + un sous-domaine par automate** (ex. `client1.domaine.fr`,
`client2.domaine.fr`). Chaque Pi a son propre `CLOUDFLARE_TUNNEL_TOKEN`.

### Arrêter l'accès distant
```bash
sudo docker compose -f docker-compose.pi.yml stop cloudflared
```
