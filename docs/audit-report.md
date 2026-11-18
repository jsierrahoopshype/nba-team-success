# Team Success data audit

Run `python scripts/audit.py` (numbers saved in `data/audit.json`, re-checked by `tests/test_audit.py`). Every fault below lists the rows it touches, the cause and the fix.

## Jordan regression check

| Measure | Expected | Got |
|---|---|---|
| With him | 706–366, 1,072 games, 65.9%, W − L +340 | 706–366, 1,072 games, 65.9%, W − L +340 |
| Without him (published window proxy) | 63–95 in 158 games, 39.9% | 63–95 in 158 games, 39.9% |
| Gap (unrounded rates) | +26.0 pp | +26.0 pp (+25.9848) |
| Winning seasons | 10 | 10 |
| Playoff trips | 13 | 13 |
| Titles | 6 | 6 |
| Average final finish | 7.4 | 7.4 (mean of 15 seasons' RNK) |
| Without him, between his first and last game (appearance span) | n/a | 26–59 in 85 games, 30.6%, gap +35.3 pp |

Season by season (the rows behind every number above):

| Season | Team | His games | With | Without (window) | Without (span) | First / last game | Team W–L | Playoffs | RNK |
|---|---|---|---|---|---|---|---|---|---|
| 1984-85 | Chicago Bulls | 82 | 38–44 | 0–0 | 0–0 | 1984-10-26 / 1985-04-13 | 38–44 | First Round | 14 |
| 1985-86 | Chicago Bulls | 18 | 9–9 | 21–43 | 21–43 | 1985-10-25 / 1986-04-13 | 30–52 | First Round | 16 |
| 1986-87 | Chicago Bulls | 82 | 40–42 | 0–0 | 0–0 | 1986-11-01 / 1987-04-17 | 40–42 | First Round | 15 |
| 1987-88 | Chicago Bulls | 82 | 50–32 | 0–0 | 0–0 | 1987-11-07 / 1988-04-24 | 50–32 | Conf Semis | 6 |
| 1988-89 | Chicago Bulls | 81 | 47–34 | 0–1 | 0–1 | 1988-11-04 / 1989-04-23 | 47–35 | Conf Finalist | 4 |
| 1989-90 | Chicago Bulls | 82 | 55–27 | 0–0 | 0–0 | 1989-11-03 / 1990-04-22 | 55–27 | Conf Finalist | 3 |
| 1990-91 | Chicago Bulls | 82 | 61–21 | 0–0 | 0–0 | 1990-11-02 / 1991-04-21 | 61–21 | Champion | 1 |
| 1991-92 | Chicago Bulls | 80 | 67–13 | 0–2 | 0–2 | 1991-11-01 / 1992-04-19 | 67–15 | Champion | 1 |
| 1992-93 | Chicago Bulls | 78 | 56–22 | 1–3 | 1–3 | 1992-11-06 / 1993-04-25 | 57–25 | Champion | 1 |
| 1994-95 | Chicago Bulls | 17 | 13–4 | 34–31 | 0–0 | 1995-03-19 / 1995-04-23 | 47–35 | Conf Semis | 8 |
| 1995-96 | Chicago Bulls | 82 | 72–10 | 0–0 | 0–0 | 1995-11-03 / 1996-04-21 | 72–10 | Champion | 1 |
| 1996-97 | Chicago Bulls | 82 | 69–13 | 0–0 | 0–0 | 1996-11-01 / 1997-04-19 | 69–13 | Champion | 1 |
| 1997-98 | Chicago Bulls | 82 | 62–20 | 0–0 | 0–0 | 1997-10-31 / 1998-04-18 | 62–20 | Champion | 1 |
| 2001-02 | Washington Wizards | 60 | 30–30 | 7–15 | 4–10 | 2001-10-30 / 2002-04-02 | 37–45 | missed | 19 |
| 2002-03 | Washington Wizards | 82 | 37–45 | 0–0 | 0–0 | 2002-10-30 / 2003-04-16 | 37–45 | missed | 20 |

- **Why Chicago's 34–31 before his March 1995 return counts.** Under the published proxy a player with one team in a season has a window of the whole season. Jordan played only for Chicago in 1994-95, so every Bulls game he did not play (the 65 before his first game on 1995-03-19) counts as "without him". The appearance-span definition starts at his first game, so those 65 games drop out.
- **Why 1993-94 is outside the proxy.** He has no appearance for any team that season (he was retired), so he has no team-season and no window. The proxy only opens a window for a team-season he appeared in.
- **Winning seasons 10**: team W–L above .500 in 1987-88 to 1992-93 and 1994-95 to 1997-98 (Chicago 38–44 in 1984-85, 30–52 in 1985-86, 40–42 in 1986-87 and Washington 37–45 twice are not). **Playoff trips 13**: every Chicago season. **Titles 6**: 1990-91 to 1992-93, 1995-96 to 1997-98. **Average finish 7.4** = (14 + 16 + 15 + 6 + 4 + 3 + 1 + 1 + 1 + 8 + 1 + 1 + 1 + 19 + 20) / 15. The leaderboards call the same `analysis.summary()` rules.

## How with/without works now

Two definitions, computed for every player-team-season, both reproducible from `data/gamelog/`:

1. **Team-season window (the published proxy, the headline number).** One team all season: the whole season. Traded: the first team's window ends the day before his first game for the next team; the next window starts the day after his last game for the previous team.
2. **Appearance span (dated by his own games).** The team's games he missed between his first and last game for that team, per stint. No game before he arrived or after he left can count, and no game counts for two teams. It can miss real absences at the start or end of a stint (an injury before his first game).

No free, allowed source has historical signing, waiver or trade dates, so neither definition uses them. Pages show the proxy, with the span figure and its definition next to it.

## Faults and limits found

### 1. Appearances a player could not have made (fixed)

- **Rows affected:** 252 box-score rows in 59 player-team-seasons. Largest: Dwight Jones 1979-80 HOU (44 rows); Edgar Jones 1984-85 SAS (21 rows); Clemon Johnson 1982-83 IND (18 rows); George Mikan 1950-51 WSC (17 rows); Don Collins 1980-81 ATL (17 rows); Johnny Davis 1979-80 UTA (12 rows); Michael Cooper 1982-83 LAC (12 rows); John Murphy 1946-47 GSW (9 rows); George Mikan 1950-51 SAC (8 rows); Elmore Smith 1976-77 CLE (8 rows); Bingo Smith 1979-80 CLE (7 rows); Reggie Johnson 1981-82 SAS (7 rows). Every row is listed on How we count and in data/step0.json (`impossible_rows_dropped`).
- **Cause:** Source box scores file one player's line under another player's ID or on the wrong team. The signs: games for team B between two games he played for team A with no team-A game missed in between; appearances for two teams on one day (13 were the same game, both sides); stints made only of 0-minute rows in games where minutes were kept. Before the fix, 44 players' games by opponent did not add up to their career record, and windows broke into dozens of one-day pieces (George Mikan 1950-51 had 22).
- **Fix:** `drop_impossible()` in build_history.py drops the 0-minute rows among the flagged ones, or, in seasons without minutes, the rows of the team he played fewer games for. After the fix every player's opponent rows add up and no player is on two teams in one day. Rows confirmed by the lineup data (1996-97 on) are never treated as 0-minute.

### 2. Games before a one-team player's first appearance count as "without him"

- **Rows affected:** 6,734 player-team-seasons, 127,111 team games. Largest: Jack Haley 1995-96 CHI (81 games); Geert Hammink 1993-94 ORL (81 games); Linton Townes 1984-85 SAS (81 games); Walker Russell Sr 1987-88 DET (81 games); David Wingate 2000-01 OKC (81 games).
- **Cause:** The proxy window is the whole season for a one-team player. A late signing, a rookie called up in midseason or a return from injury all look the same in box scores.
- **Fix:** Kept as the labeled proxy (it is the published method). Every row now also carries the appearance-span record (`sw`, `sl`), which excludes these games, and the page shows both with their definitions.

### 3. Games after a one-team player's last appearance count as "without him" (cuts, season-ending injuries)

- **Rows affected:** 7,444 player-team-seasons, 154,161 team games. Largest: Larry Wright 1981-82 DET (81 games); Walt Wesley 1975-76 LAL (81 games); Stan Washington 1974-75 WAS (81 games); Joao Vianna 1991-92 DAL (81 games); Robert Smith 1980-81 CLE (81 games).
- **Cause:** The window runs to season's end; box scores cannot show the day he was waived.
- **Fix:** Same as above: proxy kept and labeled, appearance span added.

### 4. Days between two teams count for both teams

- **Rows affected:** 5,185 traded player-team-seasons, 48,524 team games. Largest: Walter Tavares 2016-17 ATL (79 games); Walter Tavares 2016-17 CLE (78 games); Ronald Dupree 2007-08 OKC (73 games); Sedric Toney 1985-86 ATL (72 games); Ronald Dupree 2007-08 DET (72 games).
- **Cause:** The first window ends the day before his first game for the new team and the new window starts the day after his last game for the old one, so the days in between are inside both.
- **Fix:** Appearance span never overlaps. Proxy kept, labeled.

### 5. Players with no missed games

- **Rows affected:** 16 careers have 0 games without him under the proxy.
- **Cause:** One-team seasons where he played every game.
- **Fix:** Empty samples show N/A, never 0.0% or a gap; the gap leaderboards require a minimum on both sides.

### 6. RNK ordering

- **Rows affected:** 0 team-seasons where the CSV's RNK differs from champion, runner-up, then playoff round, then win % (ties share a rank). 365 rows share a rank with another team.
- **Cause:** RNK comes from the owner's sheet (RNK PTS = round points + win %).
- **Fix:** We display the CSV's RNK unchanged (same source on player pages and season boards); the audit re-derives it every run. League size per season goes next to every rank: 1946-47 11, 1949-50 17, 1950-51 11, 1954-55 8, 1961-62 9, 1966-67 10, 1967-68 12, 1976-77 22, 1988-89 25, 1989-90 27, 1995-96 29, 2004-05 30, 30 since 2004-05.

### 7. Playoff result vs playoff games

- **Rows affected:** 2 team-seasons disagree: DET 1954 Fort Wayne Pistons standings 'missed', games SAC 0-2, LAL 0-2; NYK 1954 New York Knicks standings 'missed', games BOS 0-2, PHI 0-2.
- **Cause:** Play-in and tiebreaker games sit in the playoff game type in some seasons.
- **Fix:** Team result always comes from the standings' Playoffs column; series lists come from the games and are shown as games, not as a round.

### 8. Playoff "series" that are not best-of series

- **Rows affected:** 0 team pairs.
- **Cause:** Early playoff formats had round-robin groups and tiebreakers; we group playoff games by opponent.
- **Fix:** These show as games played against that opponent, not as a series won or lost; series records on the opponent table count only pairs decided by a series.

### 9. Team game counts vs standings

- **Rows affected:** 2 team-seasons: Milwaukee Hawks 1954 71 vs 72; Baltimore Bullets 1954 71 vs 72.
- **Cause:** One 1953-54 Milwaukee-Baltimore game is missing from the box scores.
- **Fix:** Team records use the standings; with/without uses the games we have (the two can differ by that one game).

### 10. Duplicate games and rows

- **Rows affected:** Duplicate game IDs in the raw files: none. Duplicate box-score rows: none. Same matchup twice on one day after clean-up: 0. A player on both sides of one game: 0.
- **Cause:** n/a
- **Fix:** Nothing to fix.

### 11. Opponent rows vs career totals

- **Rows affected:** 0 of 5,103 players' opponent rows do not add up to the career record.
- **Cause:** Checks every regular-season game he appeared in, grouped by opponent franchise.
- **Fix:** Nothing to fix.

### 12. Standings file quirks

- **Rows affected:** Header text inside a data cell: none. BRK instead of BKN: BRK 2025, BRK 2026.
- **Cause:** Hand-edited spreadsheet.
- **Fix:** We never read the shifted cells (only Win, Losses, Conference, Division, positions, Playoffs, RNK). BRK is read as BKN.

## Shortened seasons and early leagues

- 1998-99: 29 teams, games per team 50. Win % and RNK use each team's own games, so unequal schedules (2019-20) compare by win %.
- 2011-12: 30 teams, games per team 66. Win % and RNK use each team's own games, so unequal schedules (2019-20) compare by win %.
- 2019-20: 30 teams, games per team 64, 65, 66, 67, 71, 72, 73, 74, 75. Win % and RNK use each team's own games, so unequal schedules (2019-20) compare by win %.
- 2020-21: 30 teams, games per team 72. Win % and RNK use each team's own games, so unequal schedules (2019-20) compare by win %.
- League size by season ranges from 8 to 30. Final finish is shown as "#8 of 30" with that season's size, and the league-size-adjusted view uses (rank − 1) / (teams − 1), 0 = champion, 1 = last.

## Coverage, and the Nov. 16 question

- Career numbers: completed seasons, 1946-47 to 2025-26 (box scores + standings).
- Current season: 2026-27, 205 games through 2026-11-16, from Ramiro lineups (nba-boxscores has no 2026-27 data yet). Shown in its own block and on the daily boards, never added to career totals.
- Why the board said Nov. 16 while Jordan's page said 2025-26: both were right, they describe different scopes. Jordan's page states the career scope (completed seasons only; 2026-27 is not in any career total until it ends). The board is the current season, and its date is the last game in Ramiro's 2026-27 files at the last nightly run (games of a US evening land in those files the following day). The copy now names both scopes on every page: "Career: 1946-47 to 2025-26 regular seasons. 2026-27: games through <date>, shown separately."
- On/off, starts and close games: 1996-97 on. Minutes not kept in 1946-47, 1947-48, 1948-49, 1949-50, 1950-51.
- Ramiro gaps: 2024-25 regular 1230/1230, playoffs 83/84
- Play-in games (game type 5) are in neither the regular season nor the playoffs (2020-21: 6, 2021-22: 6, 2022-23: 6, 2023-24: 6, 2024-25: 6, 2025-26: 6).
