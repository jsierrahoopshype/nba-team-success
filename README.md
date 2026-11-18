# Team Success (HoopsMatic)

Every NBA player's team record with him and without him, every season since 1946-47.
Served at https://hoopsmatic.com/team-success/.

## Data pipeline

```
bash scripts/fetch_sources.sh          # public repos + Ramiro's Parquet files into _src/ (git-ignored)
python scripts/build_history.py        # rebuilds everything in data/ (about 1 minute)
python scripts/step0_report.py         # docs/step0-report.md
python -m pytest tests/ -q             # sanity checks on the committed data
```

| File | What it is |
|---|---|
| `data/team_standings.csv` | the owner's standings file (records, finish, RNK, playoff finish) |
| `data/franchise_map.json` | (era code, season) -> current franchise + the team's real name that season |
| `data/player_ids.json` | NBA personId -> stable slug (Career Map style) + display name + headshot file |
| `data/team_seasons.json` | one row per franchise-season: record, finish, RNK, playoff series |
| `data/players.json` | one row per player-team-season: games, with/without records, on/off, starts, close games; best duos; accolade score |
| `data/step0.json` | the numbers behind `docs/step0-report.md` |

No keys or tokens are needed anywhere.
