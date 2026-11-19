# Team Success: Step 0 report

Read-only checks on the sources, run before building the pages. Every number below comes from `scripts/build_history.py` (saved in `data/step0.json`) and the main ones are re-checked by `tests/test_step0.py` on every run.

## Sources (public, no tokens)

| Source | Version used | What we take |
|---|---|---|
| aderoa/nba-boxscores | 05efb8f 2026-11-17 | every game and box score, 1946-47 to 2025-26 |
| jsierrahoopshype/nba-player-data | caf7829 2026-11-18 | RS-Stats.csv (names), awards.json (honors) |
| jsierrahoopshype/hh-teammates | b9767c3 2026-11-17 | accolade weights (`scores`) and the scoring rules |
| ramirobentes/nbadatar (data in ramirobentes/nba_data releases) | Parquet files of 2026-11-18 | lineups and possessions, 1996-97 on |
| jsierrahoopshype/nba-headshots | 9d46952d 2026-11-16 | face-fill headshots, team slugs |
| jsierrahoopshype/nba-career-map | a7f4d78 2026-11-17 | era names cross-check, player slugs |
| team_standings.csv (attached) | committed as data/team_standings.csv | team records, finish, RNK, playoff finish |

## team_standings.csv: verified facts

- 1723 team-seasons, 1946-47 to 2025-26.
- **Team ABR is the current franchise code** for old seasons: `SAC 1956` is the Rochester Royals, `GSW 1947` the Philadelphia Warriors, `OKC 1975` the Seattle SuperSonics. The `Team` column is today's name, so the pages never show it; they use the era name from `data/franchise_map.json` instead.
- **W-L% is mixed**: 1459 rows written like `439`, 264 like `0.439`. We never read it; win % is always Win / (Win + Losses).
- **Trailing columns are shifted**: the ATL 2024 row ends `Champion, 100000` although the Hawks lost in the play-in (`Playoffs` = `Play-In`). Those last two columns are a pasted lookup table (round name, tier points), not that team's result. We ignore them and use the `Playoffs` column plus the playoff games themselves.
- **RNK is the owner's season ranking**: champion first, then runner-up, then by playoff round reached, then by win % (play-in teams rank above non-playoff teams; ties share a rank). `RNK PTS` holds the tier points behind it (100,000 champion, 10,000 finalist, 1,000 conference finalist, 100 semis, 10 first round, 1 play-in, plus win %). Sample, 1974-75:

| Season | Team | W-L | Playoffs | RNK | RNK PTS |
|---|---|---|---|---|---|
| 1974-75 | Golden State Warriors | 48-34 | Champion | 1 | 100,000.59 |
| 1974-75 | Washington Bullets | 60-22 | Finalist | 2 | 10,000.73 |
| 1974-75 | Boston Celtics | 60-22 | Conf Finalist | 3 | 1,000.73 |
| 1974-75 | Chicago Bulls | 47-35 | Conf Finalist | 4 | 1,000.57 |
| 1974-75 | Buffalo Braves | 49-33 | Conf Semis | 5 | 100.60 |
| 1974-75 | Kansas City-Omaha Kings | 44-38 | Conf Semis | 6 | 100.54 |
| 1974-75 | Seattle SuperSonics | 43-39 | Conf Semis | 7 | 100.52 |
| 1974-75 | Houston Rockets | 41-41 | Conf Semis | 8 | 100.50 |
| 1974-75 | Detroit Pistons | 40-42 | First Round | 9 | 10.49 |
| 1974-75 | New York Knicks | 40-42 | First Round | 9 | 10.49 |

  Every season has exactly one champion and it has RNK 1 (tested).
- **BRK vs BKN**: Brooklyn is `BRK` in the 2 rows for 2024-25 and 2025-26 and `BKN` everywhere else. We read `BRK` as `BKN`.
- **2025-26 has no conference/division finish** (blank `Conf Pos`, `Div Pos`, `Postition`). We compute those 120 places from W-L (ties share a place) and mark them computed.
- **The `PO-series.csv` file is not a team playoff table**: it lists each player's career series won/lost. So round, opponent and series score come from the playoff games in nba-boxscores (game ID 3rd character `4`), grouped by opponent.

## a. Regular-season games: nba-boxscores vs standings

Raw comparison (games in nba-boxscores with game ID type `2` vs the sum of wins in the standings): **74 of 80 seasons match**. Off by 1-2 in 1947-48, 1949-50, 1953-54, 1955-56, 1956-57, 2012-13.

| Season | Box score games | Standings | Teams off |
|---|---|---|---|
| 1947-48 | 194 | 192 | Baltimore Bullets 49 vs 48, Chicago Stags 50 vs 48, Washington Capitols 49 vs 48 |
| 1949-50 | 563 | 561 | Chicago Stags 69 vs 68, Fort Wayne Pistons 69 vs 68, Minneapolis Lakers 69 vs 68, Rochester Royals 69 vs 68 |
| 1953-54 | 323 | 324 | Milwaukee Hawks 71 vs 72, Baltimore Bullets 71 vs 72 |
| 1955-56 | 290 | 288 | St. Louis Hawks 73 vs 72, Minneapolis Lakers 73 vs 72, New York Knicks 73 vs 72, Syracuse Nationals 73 vs 72 |
| 1956-57 | 290 | 288 | St. Louis Hawks 74 vs 72, Fort Wayne Pistons 73 vs 72, Minneapolis Lakers 73 vs 72 |
| 2012-13 | 1230 | 1229 | Boston Celtics 82 vs 81, Indiana Pacers 82 vs 81 |

What the extra and missing games are:

- 1948-03-23 `0024700193` WAS 72 @ CHS 75: **tiebreaker**, removed from regular-season counts.
- 1948-03-25 `0024700194` BAL 70 @ CHS 74: **tiebreaker**, removed from regular-season counts.
- 1950-03-20 `0024900564` CHS 69 @ FTW 86: **tiebreaker**, removed from regular-season counts.
- 1950-03-21 `0024900563` MNL 78 @ ROC 76: **tiebreaker**, removed from regular-season counts.
- 1956-03-15 `0025500289` NYK 77 @ SYR 82: **tiebreaker**, removed from regular-season counts.
- 1956-03-16 `0025500290` MNL 103 @ STL 97: **tiebreaker**, removed from regular-season counts.
- 1957-03-14 `0025600289` FTW 103 @ STL 115: **tiebreaker**, removed from regular-season counts.
- 1957-03-16 `0025600290` MNL 111 @ STL 114: **tiebreaker**, removed from regular-season counts.
- 2013-04-16 `0021201214` IND 0 @ BOS 0: **cancelled (0-0)**, removed from regular-season counts.
- 1953-54: one Milwaukee Hawks vs Baltimore Bullets game is **missing** from nba-boxscores (both teams have 71 games, standings say 72). Nothing to add it from, so it is left out.

After removing those 9: **79 of 80 seasons match**; only 1953-54 is off (by the missing game).

Game results that disagree with the official records (team pages show the official record; the with/without numbers use the games):

| Team-season | Standings | From box scores |
|---|---|---|
| Milwaukee Hawks 1953-54 | 21-51 | 20-51 |
| Baltimore Bullets 1953-54 | 16-56 | 16-55 |
| Baltimore Bullets 1952-53 | 15-55 | 16-54 |
| Minneapolis Lakers 1952-53 | 49-21 | 48-22 |
| Philadelphia Warriors 1950-51 | 39-27 | 40-26 |
| Washington Capitols 1950-51 | 11-24 | 10-25 |
| Boston Celtics 1946-47 | 23-37 | 22-38 |
| Philadelphia Warriors 1946-47 | 34-26 | 35-25 |

Also fixed: 10 neutral-site games in 2024-25 and 2025-26 (NBA Cup semifinals, Mexico City, Paris, London, Berlin) have `home: null` and `homeScore: null`, with both teams flagged as visitors. We fill in the other team from the box score and its score from its players' points:

- 2024-11-02 `0022400147` WAS 98 - MIA 118
- 2024-12-14 `0022401229` ATL 102 - MIL 110
- 2024-12-14 `0022401230` OKC 111 - HOU 96
- 2025-01-23 `0022400621` SAS 140 - IND 110
- 2025-01-25 `0022400633` SAS 98 - IND 136
- 2025-11-01 `0022500147` DAL 110 - DET 122
- 2025-12-13 `0022501229` ORL 120 - NYK 132
- 2025-12-13 `0022501230` OKC 109 - SAS 111
- 2026-01-15 `0022500578` MEM 111 - ORL 118
- 2026-01-18 `0022500602` MEM 126 - ORL 109

## b. Franchise map

`data/franchise_map.json` maps every (era code, season) in nba-boxscores to the current franchise code and the team's real name that season: 74 era codes, 80 name eras. Examples: 1967-68 `SDR` -> HOU, San Diego Rockets; 1996-97 `VAN` -> MEM, Vancouver Grizzlies; 2009-10 `NJN` -> BKN, New Jersey Nets; 2011-12 `CHA` -> CHA, Charlotte Bobcats; 2005-06 `NOK` -> NOP, New Orleans/Oklahoma City Hornets.

- Codes we could not map: **none**. Every team-season in the games is in the standings and vice versa.
- **Bug in nba-boxscores**: its `data/team_codes.json` maps `BOM` to `BAL`. `BOM` (1946-47 to 1949-50) is the St. Louis Bombers (`STB` in the standings), not the Baltimore Bullets. Our map uses STB. Worth fixing upstream; we did not touch that repo.
- `WAS` means two different franchises: the Washington Capitols (1946-47 to 1950-51, `WSC`) and the Bullets/Wizards (from 1974-75). `DN` (1949-50) is the old Denver Nuggets (`DNN`), not today's.
- Names checked against nba-career-map `data/nba_team_index.json`: every Career Map era name is used. Names we use that Career Map does not have: Anderson Packers, Chicago Stags, Cleveland Rebels, Detroit Falcons, Indianapolis Jets, Indianapolis Olympians, Los Angeles Clippers, New Orleans/Oklahoma City Hornets, Pittsburgh Ironmen, Providence Steamrollers, Sheboygan Red Skins, St. Louis Bombers, Toronto Huskies, Washington Capitols, Waterloo Hawks. All but two are defunct teams with no Career Map page (their names stay unlinked). "New Orleans/Oklahoma City Hornets" (2005-06, 2006-07) is the name the team used those seasons; Career Map files them under New Orleans Hornets. "Los Angeles Clippers" is used for 1984-85 to 2014-15 and "LA Clippers" from 2015-16 (the team's rebrand); Career Map uses "LA Clippers" throughout. Both still link to the same Career Map team page.

## c. Player identity

Box-score players (personId + name) matched to RS-Stats.csv names per season + franchise, accents and punctuation stripped on both sides. Passes, in order: exact name, name without Jr./Sr./II and birth-year tags, same last name + first initial, the only player on that team-season with that last name (RS-Stats uses nicknames: Johnny Kerr = "Red Kerr", Rod Hundley = "Hot Rod Hundley"), close spelling (similarity 0.85+). A small alias list covers renamed players (Enes Freedom = Enes Kanter, Timothe Luwawu-Cabarrot = Timothe Luwawu).

- Player-team-seasons: **28557 of 28803 matched (99.2%)**.
- Players: 5103; with an RS-Stats name: 5056; with a Career Map page under the same slug: 5074.
- Players with 20+ games and **no RS-Stats name at all: 7**, all 2025-26 rookies missing from RS-Stats (their box-score name is used, and it matches Career Map):
  - Kasparas Jakučionis (53 games, personId 1642857)
  - Lachlan Olbrich (37 games, personId 1642950)
  - Kam Jones (37 games, personId 1642880)
  - Ethan Thompson (32 games, personId 1630679)
  - Jahmai Mashack (31 games, personId 1642942)
  - Adou Thiero (25 games, personId 1642876)
  - Alijah Martin (23 games, personId 1642918)
- Single seasons with 20+ games that did not match by name for that team (85 rows). The player is still identified by personId from his other seasons; these are mostly 1950s RS-Stats rows filed under a different team or season. Full list at the end of this report.
- `data/player_ids.json`: one stable slug per personId. Career Map rule (`Nikola Jokić` -> `nikola-jokic`), and Career Map's birth-year names for same-name players (`charles-smith-1965`). 50 slugs carry a year or id suffix: bob-duffy-1922, bob-duffy-1940, bobby-jones-1984, brandon-williams-1975, cedric-henderson-1965, cedric-henderson-1975, charles-jones-1957, charles-jones-1962, charles-jones-1975, charles-smith-1965, charles-smith-1967, charles-smith-1975, chris-smith-1970, chris-smith-1987, chris-wright-1988, chris-wright-1989, dee-brown-1968, dee-brown-1984, don-smith-1920, don-smith-1951, freddie-lewis-1921, freddie-lewis-1943, george-johnson-1948, george-johnson-1956, george-king-1928, greg-smith-1947, greg-smith-1991, jack-turner-1930, jack-turner-1939, johnny-davis-1955, ken-johnson-1962, ken-johnson-1978, kevin-porter-1950, larry-johnson-1954, larry-johnson-1969, mark-davis-1963, mark-davis-1973, mark-jones-1961, mark-jones-1975, michael-smith-1965, michael-smith-1972, mike-brown-1963, mike-davis-1946, mike-davis-1956, mike-james-1975, mike-james-1990, reggie-williams-1964, reggie-williams-1986, tony-mitchell-1989, tony-mitchell-1992.

## Honors: awards.json

- Source: `awards.json` in nba-player-data (10,652 rows, 1946-47 to 2026-27), the same file the Player Comparison tool reads. It replaced Awards.csv, which stops at 2024-25. Fields: "PLAYER / COACH", "AWARD", "YEAR", "TEAM".
- Rows by season: 2024-25 203, 2025-26 207, 2026-27 8; All-Stars: 2024-25 26, 2025-26 28, 2026-27 0.
- Names are matched to players on the RS-Stats name (else the display name), as before. Player names in the newest seasons that match no player (coach awards left out): 2025-26: Deriq Queen; 2026-27: none.

## d. "Did he play?"

Rule: appeared = minutes > 0 OR any counting stat > 0; when minutes were never recorded, appeared = he has a box-score row. Minutes are recorded game by game, not season by season, so we apply the rule **per team-game**: if any player of that team has minutes in that game, the minutes rule applies; otherwise a row counts as an appearance.

- Minutes never recorded: **1946-47 to 1950-51** (row present = appeared).
- Minutes recorded in some games only: **1951-52 to 1975-76** (share of team-games with minutes rises from 13% in 1951-52 to 95% in 1975-76).
- Minutes recorded in (almost) every game: **1976-77 to 2025-26**.
- **Change from the brief, flagged for you**: from 1996-97, a row with 0 minutes and no stats is usually NOT a DNP. Ramiro's lineups put 2526 of those player-games (about 60-140 a season) on the floor: seconds-long cameos whose minutes round down to 0. We count those as appearances. Only 107 zero rows from 1996-97 on stay excluded. Switch: `COUNT_RAMIRO_CAMEOS` in `scripts/build_history.py`.

## e. Ramiro's data

Seasons 1996-97 to 2025-26, regular season and playoffs, plus 2026-27 regular season (updated daily; checked through games of 2026-11-16). Files are Parquet releases at github.com/ramirobentes/nba_data (the nbadatar R package just downloads them).

| File | What we use it for |
|---|---|
| `lineup_stats_<regular/playoffs>_<season>.parquet` | one row per stint: both 5-man lineups (NBA person IDs), seconds, possessions and points for both teams. **On/off per 100** (points and possessions with him on vs his team's other stints in the same games) and **starters** (the team's first stint of the game). |
| `possessions_<...>_<season>.parquet` | one row per possession with the score at its start, the period, the clock and both lineups. **Close games** = a possession in the last 5:00 of the 4th quarter or any overtime with the margin at 5 or fewer; "on the floor" = in either lineup on one of those possessions. |
| `pbp_<...>_<season>.parquet` | not used (the two tables above already carry what we need, at a fraction of the size). |

Coverage: lineups for every regular-season game in 30 of 30 seasons. Gaps: 2024-25 playoffs 83 of 84 games. Person IDs match nba-boxscores personId exactly, so no name matching is needed.

## f. Headshots (option C)

nba-headshots README (Oct 26 2026): `players/headshots/face-fill/` is "THE HoopsMatic headshot: the face fills the frame, chin just inside the bottom, no neck line, no background. 160x160 transparent WebP, show it in a circle". The newest section, Teammates (hh-teammates `build_teammates.py`), uses exactly those files with this CSS: `.hs{width:72px;height:72px;border-radius:50%;overflow:hidden;object-fit:cover;background:#e8e8ed}` and the player's initials in the same circle when there is no file.

- face-fill files: 1883. Players in Team Success with a photo: **1779 of 5103** (file names are `<NBA personId>-<name>.webp`, and personId is the box-score id, so matching is exact).
- Teammates loads them from jsierrahoopshype.github.io. The brief forbids third-party requests from the visitor's browser and github.io anywhere, so Team Success **copies the face-fill files it needs into this repo** (`assets/hs/`) and serves them from hoopsmatic.com paths. Same files, same look. Missing photo: an empty circle on light grey (#e8e8ed), never black.

## Expected results (also in tests/test_step0.py)

- Worst record, all-time: top count is 5: John Block, Johnny Green. Matches.
- Worst record since 1976-77: nobody above 3; 17 players at 3: Alec Burks, Benoit Benjamin, Bojan Bogdanovic, Brad Miller, Bryant Reeves, Christian Wood, DJ Augustin, Danuel House, Geoff Huston, Greg Anthony, Joe Wolf, KJ Martin, Kevin Knox, Marvin Bagley, Pete Chilcutt, Sean Rooks, Tim Legler. Matches (the 10 named in the brief all had 20+ games each time).
- 60-win pace (win % >= 60/82 = .732): Kareem Abdul-Jabbar 8, Tim Duncan 7, Manu Ginobili 7, Danny Green 7, Tony Parker 7. Matches.

## Season-level unmatched rows (20+ games)

| Season | Team | Box-score name | Games |
|---|---|---|---|
| 1949-50 | Waterloo Hawks | Bob Tough | 21 |
| 1949-50 | Waterloo Hawks | Charley Shipp | 22 |
| 1949-50 | Waterloo Hawks | Dick Mehen | 62 |
| 1949-50 | Waterloo Hawks | Don Boven | 62 |
| 1949-50 | Waterloo Hawks | Gene Stump | 25 |
| 1949-50 | Waterloo Hawks | Harry Boykoff | 61 |
| 1949-50 | Waterloo Hawks | Jack Smiley | 47 |
| 1949-50 | Waterloo Hawks | Johnny Payak | 35 |
| 1949-50 | Waterloo Hawks | Leo Kubiak | 62 |
| 1949-50 | Waterloo Hawks | Stan Patrick | 34 |
| 1949-50 | Waterloo Hawks | Ward Gibson | 29 |
| 1949-50 | Waterloo Hawks | Wayne See | 60 |
| 1950-51 | Baltimore Bullets | Chuck Halbert | 33 |
| 1954-55 | Fort Wayne Pistons | Bob Houbregs | 52 |
| 1954-55 | Syracuse Nationals | Connie Simmons | 25 |
| 1954-55 | Milwaukee Hawks | Frank Selvy | 60 |
| 1954-55 | Philadelphia Warriors | Jackie Moore | 20 |
| 1954-55 | Philadelphia Warriors | Ken Murray | 59 |
| 1955-56 | Fort Wayne Pistons | Jim Holstein | 27 |
| 1956-57 | Fort Wayne Pistons | Alex Hannum | 22 |
| 1956-57 | Syracuse Nationals | Bob Harrison | 56 |
| 1988-89 | Washington Bullets | Charles Jones | 53 |
| 1988-89 | Washington Bullets | Charles Jones | 43 |
| 2025-26 | Toronto Raptors | A.J. Lawson | 24 |
| 2025-26 | Dallas Mavericks | AJ Johnson | 23 |
| 2025-26 | Los Angeles Lakers | Adou Thiero | 25 |
| 2025-26 | Toronto Raptors | Alijah Martin | 23 |
| 2025-26 | Minnesota Timberwolves | Ayo Dosunmu | 24 |
| 2025-26 | LA Clippers | Bennedict Mathurin | 26 |
| 2025-26 | Atlanta Hawks | CJ McCollum | 41 |
| 2025-26 | Philadelphia 76ers | Cameron Payne | 22 |
| 2025-26 | Charlotte Hornets | Coby White | 21 |
| 2025-26 | Chicago Bulls | Collin Sexton | 26 |
| 2025-26 | Atlanta Hawks | Corey Kispert | 39 |
| 2025-26 | Golden State Warriors | De'Anthony Melton | 49 |
| 2025-26 | Cleveland Cavaliers | Dennis Schröder | 30 |
| 2025-26 | Phoenix Suns | Devin Booker | 64 |
| 2025-26 | Houston Rockets | Dorian Finney-Smith | 37 |
| 2025-26 | Los Angeles Lakers | Drew Timme | 27 |
| 2025-26 | Indiana Pacers | Ethan Thompson | 32 |
| 2025-26 | Atlanta Hawks | Gabe Vincent | 24 |
| 2025-26 | Charlotte Hornets | Grant Williams | 36 |
| 2025-26 | Chicago Bulls | Guerschon Yabusele | 26 |
| 2025-26 | Washington Wizards | Jaden Hardy | 23 |
| 2025-26 | Detroit Pistons | Jaden Ivey | 33 |
| 2025-26 | Memphis Grizzlies | Jahmai Mashack | 31 |
| 2025-26 | Oklahoma City Thunder | Jalen Williams | 33 |
| 2025-26 | Phoenix Suns | Jamaree Bouyea | 46 |
| 2025-26 | Cleveland Cavaliers | James Harden | 26 |
| 2025-26 | Oklahoma City Thunder | Jared McCain | 30 |
| 2025-26 | Orlando Magic | Jevon Carter | 30 |
| 2025-26 | Atlanta Hawks | Jock Landale | 23 |
| 2025-26 | Utah Jazz | John Konchar | 26 |
| 2025-26 | New York Knicks | Jose Alvarado | 28 |
| 2025-26 | Charlotte Hornets | Josh Green | 58 |
| 2025-26 | Indiana Pacers | Kam Jones | 37 |
| 2025-26 | Miami Heat | Kasparas Jakučionis | 53 |
| 2025-26 | Sacramento Kings | Keegan Murray | 23 |
| 2025-26 | Oklahoma City Thunder | Kenrich Williams | 56 |
| 2025-26 | Cleveland Cavaliers | Keon Ellis | 29 |
| 2025-26 | Detroit Pistons | Kevin Huerter | 25 |
| 2025-26 | New York Knicks | Kevin McCullar Jr. | 21 |
| 2025-26 | Dallas Mavericks | Khris Middleton | 29 |
| 2025-26 | Sacramento Kings | Killian Hayes | 23 |
| 2025-26 | Indiana Pacers | Kobe Brown | 27 |
| 2025-26 | Chicago Bulls | Lachlan Olbrich | 37 |
| 2025-26 | Los Angeles Lakers | LeBron James | 60 |
| 2025-26 | Chicago Bulls | Leonard Miller | 27 |
| 2025-26 | Los Angeles Lakers | Luke Kennard | 32 |
| 2025-26 | Golden State Warriors | Malevy Leons | 25 |
| 2025-26 | Detroit Pistons | Marcus Sasser | 38 |
| 2025-26 | Dallas Mavericks | Marvin Bagley III | 22 |
| 2025-26 | Indiana Pacers | Micah Potter | 47 |
| 2025-26 | Orlando Magic | Moritz Wagner | 36 |
| 2025-26 | Chicago Bulls | Nick Richards | 20 |
| 2025-26 | Brooklyn Nets | Ochai Agbaji | 20 |
| 2025-26 | Utah Jazz | Oscar Tshiebwe | 27 |
| 2025-26 | Milwaukee Bucks | Ousmane Dieng | 30 |
| 2025-26 | Philadelphia 76ers | Paul George | 37 |
| 2025-26 | Chicago Bulls | Rob Dillingham | 30 |
| 2025-26 | Portland Trail Blazers | Scoot Henderson | 30 |
| 2025-26 | Oklahoma City Thunder | Shai Gilgeous-Alexander | 68 |
| 2025-26 | Memphis Grizzlies | Taylor Hendricks | 26 |
| 2025-26 | Miami Heat | Tyler Herro | 33 |
| 2025-26 | Memphis Grizzlies | Walter Clayton Jr. | 24 |

