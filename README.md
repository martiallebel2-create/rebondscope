# RebondScope

Application web tres simple pour suivre automatiquement les niveaux de veille sur:

- Tesla
- Palantir
- Nvidia
- AMD
- Amazon
- Meta
- Stellantis
- FDJ

L'application affiche pour chaque action:

- le support de la derniere seance
- le niveau d'achat apres rebond
- la resistance de la derniere seance
- le niveau de vente de verification

Tous les montants sont affiches en euros en priorite.

## Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployer en ligne

Cette application est prevue pour etre deployee facilement sur Streamlit Community Cloud.

Fichier principal:

- `app.py`

Dependances:

- `requirements.txt`

## Important

La version publique a ete volontairement simplifiee:

- une seule page
- aucun ecran Telegram
- aucun module de veille avancee visible

L'archive complete du projet est conservee localement hors de la version publique.
