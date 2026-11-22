# Position iPhone — outil local

Petit outil à lancer **sur ton PC Windows**, branché à **ton iPhone** avec un câble USB. Tu tapes une adresse exacte (par exemple *10 rue de Rivoli, Paris*), tu la vois sur la carte, tu cliques sur **Appliquer la position**, et l’iPhone croit se trouver à cet endroit.

Tu peux ouvrir la même interface **dans Safari sur l’iPhone**, tant que le téléphone reste branché au PC (c’est le PC qui envoie la position) et que les deux sont sur le **même Wi-Fi**.

Ce n’est pas un VPN et ce n’est pas une appli à installer sur l’iPhone : Apple n’autorise pas une appli iPhone à changer la position GPS du téléphone. Le PC envoie la position au téléphone via les outils développeur d’Apple (`pymobiledevice3`).

> **À savoir.** Certaines applis (jeux comme Pokémon GO, applis de rencontre, banques) détectent une position simulée et peuvent bloquer le compte. Utilise cet outil à tes risques, sur **ton** iPhone.

L’interface n’est pas publiée sur Internet. Elle tourne seulement sur ton PC et, si tu le souhaites, sur le Wi-Fi de la maison, protégée par un code secret affiché au lancement.

---

## 1. Installer Python 3.11 ou plus récent

1. Télécharge Python : [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Lance l’installateur.
3. **Coche bien la case « Add python.exe to PATH »** en bas de la première fenêtre, puis installe.
4. Ferme les fenêtres de terminal déjà ouvertes (pour qu’elles prennent le nouveau PATH).

Pour vérifier, ouvre une Invite de commandes et tape :

```bat
python --version
```

Tu dois voir `Python 3.11` ou plus récent (3.12, 3.13…).

---

## 2. Installer les pilotes Apple sur le PC

L’ordinateur doit voir l’iPhone en USB. Installe **iTunes pour Windows (version classique, pas le Microsoft Store)** :

[https://www.apple.com/itunes/download/win64](https://www.apple.com/itunes/download/win64)

Tu n’as pas besoin d’ouvrir iTunes ensuite : c’est le service « Apple Mobile Device Support » qui compte.

L’application « Appareils Apple » / « Apple Devices » du Microsoft Store peut suffire en USB, mais le paquet iTunes classique est le plus fiable d’après la documentation de `pymobiledevice3`.

Redémarre le PC si l’iPhone n’apparaît toujours pas après l’installation.

---

## 3. Brancher l’iPhone et approuver l’ordinateur

1. Déverrouille l’iPhone.
2. Branche-le au PC avec un **câble USB** (un câble « charge seule » ne marche pas : il faut un câble qui transmet des données).
3. Si l’iPhone affiche **« Approuver cet ordinateur ? »** / **« Trust This Computer? »**, appuie sur **Approuver** et entre ton code.
4. Si une fenêtre iTunes ou « Appareils Apple » s’ouvre, tu peux la laisser ou la fermer.

---

## 4. Activer le Mode développeur sur l’iPhone

Obligatoire à partir d’iOS 16. C’est réversible : tu pourras le désactiver plus tard dans les mêmes réglages.

1. Sur l’iPhone, ouvre **Réglages → Confidentialité et sécurité → Mode développeur**.
2. Active le mode, confirme, et laisse l’iPhone redémarrer.
3. Après le redémarrage, confirme encore l’écran qui s’affiche.

### Si tu ne vois pas « Mode développeur »

Le menu n’apparaît parfois qu’après une première connexion au PC. Branche l’iPhone, installe d’abord Python (étape 1), puis dans une Invite de commandes :

```bat
cd chemin\vers\iphone-location
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pymobiledevice3 amfi reveal-developer-mode
```

Cela fait seulement **apparaître** l’interrupteur, ça ne l’active pas. Retourne ensuite dans **Réglages → Confidentialité et sécurité → Mode développeur** et active-le à la main.

Si tu n’as pas de code de verrouillage, tu peux aussi essayer :

```bat
python -m pymobiledevice3 amfi enable-developer-mode
```

Cette commande redémarre l’iPhone. Elle échoue si un code est défini : dans ce cas, active le mode manuellement comme ci-dessus.

---

## 5. Lancer l’outil

1. Branche et déverrouille l’iPhone, Mode développeur déjà activé.
2. Double-clique sur **`start.bat`**.
3. Au premier lancement, les dépendances Python s’installent (il faut Internet).
4. Windows peut demander une autorisation **administrateur**. **Accepte** : cela lance `tunneld` et ouvre le **port 5000** dans le Pare-feu, **uniquement pour les réseaux privés**.
   - `tunneld` est surtout utile si ton iPhone est en **iOS 17.0 à 17.3**.
   - Sur **iOS 17.4 ou plus récent** (y compris iOS 27), `tunneld` n’est pas obligatoire, mais le pare-feu reste nécessaire pour ouvrir l’interface depuis le téléphone.
5. Ton navigateur devrait s’ouvrir sur l’interface de ce PC (lien avec un code secret). Le même lien et un **QR code** s’affichent dans la fenêtre de `start.bat` et sur la page.
6. **Laisse la fenêtre de `start.bat` ouverte** tant que tu utilises l’outil.

Si la règle de pare-feu n’a pas pu être ajoutée (tu as refusé l’administrateur, ou une erreur s’affiche), relance `start.bat` **en tant qu’administrateur** (clic droit → Exécuter en tant qu’administrateur). Vérifie aussi que le Wi-Fi du PC est bien en réseau **Privé** (voir la section suivante). Sans cela, Safari sur l’iPhone risque de ne pas joindre le PC.

---

## 6. Utiliser depuis le téléphone

L’iPhone reste **branché en USB** au PC : c’est toujours l’ordinateur qui applique la position. Safari ne sert qu’à choisir l’adresse plus confortablement, avec le téléphone à la main.

1. PC et iPhone doivent être sur le **même Wi-Fi**.
2. Sur le PC, définis ce Wi-Fi comme réseau **Privé** : **Paramètres → Réseau et Internet → Wi-Fi → ton réseau → Type de profil réseau → Privé**. Sinon le Pare-feu Windows bloque souvent le port, même avec la règle.
3. Lance `start.bat` et accepte la demande d’administrateur (pare-feu + `tunneld`).
4. Scanne le **QR code** affiché dans la fenêtre du PC ou sur la page, avec l’appareil photo de l’iPhone. Tu peux aussi taper le lien du type `http://192.168.x.x:5000/?t=…` (le `t=` est le code secret, nécessaire : sans lui, la page est refusée).
5. L’interface s’ouvre dans **Safari**. Cherche une adresse ou pose un point sur la carte, puis appuie sur **Appliquer la position**.
6. Pour la ressortir facilement : dans Safari, appuie sur **Partager** (l’icône avec la flèche) puis **Sur l’écran d’accueil**. L’interface s’installe comme une petite appli (fond sombre, icône épingle dorée), dans le même esprit que Sentinelle.

Le code secret est créé au premier lancement et enregistré dans le fichier `access_token.txt` du dossier de l’outil, pour que le raccourci reste valable après un redémarrage de `start.bat`. Ne partage pas ce lien (il donne accès à l’interface sur ton Wi-Fi). Pour changer de code, supprime `access_token.txt` et relance l’outil, puis refais le raccourci.

La localisation proposée par Safari (ou « Ma position » du téléphone) n’a pas d’importance ici : c’est le PC, via le câble, qui impose la position simulée aux autres applis.

---

## 7. Utiliser la carte

1. Tape une adresse exacte (ex. `10 rue de Rivoli, Paris`) et appuie sur **Rechercher**, ou pose un point directement sur la carte.
2. Vérifie le point affiché.
3. Appuie sur **Appliquer la position**. L’iPhone doit rester déverrouillé et branché.
4. Vérifie dans Plans / Google Maps (il peut falloir quelques secondes, parfois rouvre l’appli).

Le bandeau **Ma position actuelle simulée** rappelle le dernier point appliqué tant que la simulation est active.

---

## 8. Revenir à la vraie position

- Appuie sur **Réinitialiser (position réelle)** dans la page (sur le PC ou sur l’iPhone).
- Ou ferme la fenêtre de `start.bat` (sur iOS 17 et plus, arrêter l’outil arrête en général la simulation).
- Ou débranche le câble, puis redémarre l’iPhone si la position reste coincée.

Les autres applis peuvent mettre un moment à afficher la vraie position. Si le cercle reste flou ou coincé loin de chez toi : applique d’abord une adresse **proche de ta vraie position**, puis appuie sur Réinitialiser, ou redémarre l’iPhone. Un redémarrage de l’iPhone annule toujours la simulation.

Pour désactiver le Mode développeur plus tard : **Réglages → Confidentialité et sécurité → Mode développeur**.

---

## Versions d’iOS : ce qui change

| iPhone | Ce que fait l’outil | À prévoir |
| --- | --- | --- |
| **iOS 16 et moins** | Commande `pymobiledevice3 developer simulate-location set / clear`. La position reste jusqu’au « Réinitialiser », même si tu fermes l’outil (jusqu’au redémarrage du téléphone). | Il faut monter l’image disque développeur (**DeveloperDiskImage**) **après chaque redémarrage** de l’iPhone. L’outil lance tout seul `pymobiledevice3 mounter auto-mount` (téléchargement la première fois, Internet requis). |
| **iOS 17.0 à 17.3** (Windows) | Commande `pymobiledevice3 developer dvt simulate-location set / clear`, via un tunnel. **La position tient seulement tant que l’outil (et le processus `set`) reste lancé.** | `tunneld` doit tourner **en administrateur** : accepte la demande UAC de `start.bat`. |
| **iOS 17.4 et plus** (y compris iOS 27) | Même commande `dvt simulate-location`. **La position tient seulement tant que l’outil reste lancé.** | Le tunnel peut se créer tout seul, sans admin. `tunneld` reste utile s’il est déjà lancé, mais n’est plus obligatoire. Le pare-feu (port 5000, réseau Privé) reste nécessaire pour l’interface sur le téléphone. |

Sur iOS 17 et plus, si tu fermes `start.bat` ou que le câble se débranche, la simulation s’arrête en principe toute seule.

---

## Dépannage

**« Aucun iPhone n’est détecté »**
- Câble de données, iPhone déverrouillé, ordinateur approuvé.
- iTunes / pilotes Apple bien installés, éventuellement redémarrer le PC.
- Teste dans un terminal : `python -m pymobiledevice3 usbmux list` (après avoir activé le `.venv` comme dans l’étape 4).

**« Mode développeur » ou « service développeur »**
- Vérifie que le Mode développeur est bien activé (et confirmé après le redémarrage).
- Sur iOS 16 ou moins, attends la fin du montage de l’image disque (la première fois ça peut prendre plusieurs minutes).

**« Tunnel » / iOS 17.0–17.3**
- Relance `start.bat` et accepte la fenêtre administrateur pour `tunneld`.
- Laisse cette fenêtre `tunneld` ouverte.

**Safari sur l’iPhone n’ouvre pas l’interface / page qui tourne en boucle**
- PC et iPhone sur le **même Wi-Fi**, réseau du PC en **Privé**.
- Accepte l’administrateur au lancement pour la règle de pare-feu (port 5000).
- Utilise le lien **complet** avec `?t=…`, ou scanne le QR code (sans le code, l’accès est refusé).
- Le PC et `start.bat` doivent rester allumés. Le câble USB doit rester branché pour appliquer une position, pas forcément pour seulement afficher la page.

**La position s’applique puis revient toute seule**
- Sur iOS 17+, ne ferme pas `start.bat`.
- Garde l’iPhone déverrouillé et branché.

**`start.bat` ne trouve pas Python**
- Réinstalle Python en cochant **Add python.exe to PATH**, ferme le terminal, relance.

**L’interface ne s’ouvre pas sur le PC**
- Regarde le lien affiché dans la fenêtre de `start.bat` (il contient le code secret).
- Vérifie qu’un autre programme n’utilise pas déjà le port 5000.

---

## Fichiers du dossier

- `start.bat` — installe les dépendances, lance le pare-feu + `tunneld` (admin) et l’interface
- `elevated-setup.ps1` — script administrateur (règle de pare-feu et `tunneld`)
- `app.py` — le serveur local (Flask)
- `templates/` et `static/` — page web, styles, icônes et PWA (dans l’esprit de Sentinelle)
- `requirements.txt` — les bibliothèques Python (`flask`, `requests`, `pymobiledevice3`, `qrcode`)
- `access_token.txt` — créé au premier lancement, contient le code secret (ne pas partager)
- `apercu-telephone.html` — aperçu de l’interface téléphone (recherche et carte, sans liaison au PC)

Les adresses sont cherchées via **Nominatim / OpenStreetMap**. La carte utilise Leaflet et les tuiles OpenStreetMap.

Cet outil a été préparé pour un usage **local**, avec **ton** iPhone branché à **ton** PC. Il n’a pas été testé ici avec un vrai iPhone (pas d’appareil disponible sur la machine de développement).
