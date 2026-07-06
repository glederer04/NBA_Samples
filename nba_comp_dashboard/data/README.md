# Dashboard Data

This folder stores the cleaned player-season dataset used by the NBA Player Comp Dashboard.

## Main File

```text
player_similarity_profiles.csv
```

This CSV contains the player-season stats, percentile fields, position groups, and archetype information needed for the app to calculate NBA comps.

The dashboard reads this file locally so the live app can run quickly without calling the NBA API every time a user opens it.

If the player similarity notebook is updated later, this CSV should be regenerated and committed again so the deployed dashboard uses the newest data.
