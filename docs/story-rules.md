# Story rules: every sentence is a template

Team Success has no model-written prose. Every sentence that states a fact (player leads, daily
stories, takeaways, titles, descriptions, alt text, share text) is a template filled from data and
chosen by the rules below. A template states only what its fields prove. No template says a player
made, lifted, carried or dragged a team: it says what the record was.

## Last night in Team Success (`scripts/daily_story.py`, nightly; homepage, top)

One dated list per UTC date: "Last night in Team Success · {date} games", 4 to 10 items from the games
of the last game date in the nightly data (the season's game log in `data/current.json`, never the
previous run's totals). The first run of a date writes the list; a later run rewrites it only when
newer games arrive. Every item is one sentence from a template, with a face or a team logo, its
scope, and a link to the board row or games that prove it. Ranks use the board's own rule (default
view, qualifying group, standard competition ranking). Every `{rank}` in a sentence (this list, fun
facts, player-page leads and cards, the comparison scoreboard, share text and the share-card data) reads
"No. {r}", e.g. "for No. 128 in career wins"; a shared rank reads the same, with no "T-". A table's rank
column shows the plain number (128). Team finishes keep "#{r} of {N}".

| Priority | Item | When | Template | Proof link |
|---|---|---|---|---|
| 1 | career wins milestone | his career wins in his games (incl. 2026-27 to date) crossed 300, 400, 500 ... | "{P} reached {M} career wins in his games: {W}, {rank} on the board." | career wins board row |
| 1 | W − L milestone | his career W − L crossed a multiple of 100 (+100, +200 ... or −100 ...) | "{P} reached {M} wins minus losses: ..." | W − L board row |
| 1 | win % top 25 | among players with 500+ games, he moved into the top 25 in career win % | "{P} moved into the top 25 in career win % in his games: {pct}, {rank} among players with 500+ games." | career wins board, win % sort, 500+ games |
| 2 | notable pass (wins, W − L, win %) | the passer is in that board's top 250 (win %: top 100), AND the player passed is notable on that board: top 100 on it, a Hall of Famer (as a player, coach or contributor) or a 3+ time All-Star. Several passes for one player: only the most notable name (Hall of Famer as a player first, then most All-Star selections, then Hall of Famer as a coach or contributor, then best rank on the board) | "{P} passed {Q1} (Hall of Famer / Hall of Famer as a coach / Hall of Famer as a contributor / {n}-time All-Star)[, {Q2} and {Q3}] for {rank} in career wins / career W − L ({value})." Every player passed is named and linked, labels kept, most notable first ("A and B"; "A, B and C"); never "and k others". 8 or more passed: the 7 most notable, then "and {n} more players" linking to the board at the passer's row. | board row |
| 3 | team start | his team played last night, 8+ games, and the record is the franchise's best (worst) through that many games since a season 10+ years ago, or ever (10+ earlier seasons) | "The {team} are {W}–{L}, the franchise's best / worst start through {n} games since {season} ({W}–{L})." | the team's row in this season's standings |
| 3 | team streak | a current winning or losing streak of 5+ games that is the franchise's longest since a season 10+ years ago, or ever | "The {team} have a {k}-game winning / losing streak, the franchise's longest since {season}." | standings row |
| 4 | with / without | his team played last night; 10+ games played and 8+ missed this season; one side unbeaten or winless, or a gap of 40+ points | "The {team} are {W}–{L} without {P} and {W}–{L} with him (2026-27 to date, {g} played, {m} missed)." | his row on the with and without board at 10 and 8 |
| 5 | tonight | an active player with 15+ regular-season games against tonight's opponent (nba-editorial-bots' schedule CSV, `data/schedule_<season>.csv` on its Pages site, read the way nba-head-to-head reads it for "Tonight's duels": games on today's US Eastern date that are not final) and a win rate of .700+ or .350 or lower | "{P} faces the {opp} tonight. His teams are {W}–{L} against them in the regular season, a / an {pct} win rate." Counts completed seasons plus the season to date, like the opponent row the record links to. | his opponent row |

Picking: priority order (within a priority, the best board rank or the biggest number first), one
item per player or team, at most 4 passes, 3 team starts and 2 "tonight" items, up to 10 items. Hall of Famers come from the "Hall of
Fame" rows of awards.json (nba-player-data), matched to players by name like every other honor and
labeled "(Hall of Famer)", plus `data/hof_extra.json`: inductees from NBA.com's full list
(https://www.nba.com/news/basketball-hall-of-fame-all-time) that awards.json misses, keyed by player id.
That file holds Tommy Heinsohn (inducted as a player, labeled "(Hall of Famer)") and 21 people inducted
as a coach or contributor who also played in the NBA, labeled "(Hall of Famer as a coach)" or "(Hall of
Famer as a contributor)". Someone in both sources counts as a player inductee. These rules apply from
the Nov. 22, 2026 list; earlier lists keep their wording.

**Quiet night**: when no item qualifies the list says "Quiet night" and shows three items labeled
"From the archive" (title-winning or 60-win-pace teams on this calendar date, never repeated within
30 days). With 1 to 3 items, archive items fill it to 4. **Stale data**: when there are no new games
since the previous list, it says which games it covers.

Each list has one permalink (`stories/<date>.html`, noindex) with its share image (the headline and
the first three items); the archive (`stories/index.html`) is indexed. Lists before Nov. 19, 2026
were single stories and keep their old format. A share image is redrawn only when the text it shows
changes (the nightly keeps a hash of that text per date in `data/story_img_hash.json`); every other
image stays byte for byte as it is.

## Fun facts (`scripts/fun_facts.py`, nightly; homepage strip under the title)

6 to 8 one-sentence facts a day, each a template filled from data, each with a face (player) or a
team logo, each linking to the page or row that proves it. Same schedule as the story: the first
run of a UTC date writes the set, a later run rewrites it only when the data cutoff moved.

| Priority | Type (cap per day) | When | Template | Proof link |
|---|---|---|---|---|
| 1 | pass (0: moved to the "Last night" list) | in the games of the last game date an active player moved ahead of another player on career wins or career W − L (completed seasons + this season) and is now in the top 250; the best-ranked such pass per board | "{P} passed {Q} [and n others] last night (or "on {date}" when the data is older) for No. {r} in career wins / career wins minus losses ({value} in his games)." | the board row (`?hl=` + anchor) |
| 2 | start (2) | a team with 8+ games has the best (or worst) record through that many games since a season 5+ years ago, league-wide; else the franchise's best (worst) since a season 10+ years ago, or ever (10+ earlier seasons) | "The {team} are {W}–{L}, the [franchise's] best / worst start through {n} games since the {season} {team} ({W}–{L})." | the team's row in this season's standings |
| 3 | split (2) | 10+ games played AND 8+ missed this season, and his team is unbeaten or winless in the games he played or missed | "The {team} are {W}–0 / 0–{L} in the games {P} played / missed this season." | his row on the with and without board |
| 4 | matchup (2) | tonight's schedule: an active player with 20+ regular-season games against tonight's opponent (completed seasons plus the season to date), win rate .700+ or .350 or lower (most extreme first) | "Tonight vs the {opp}: {P}'s teams are {W}–{L} ({pct}) in his {n} regular-season games against them (incl. 2026-27 to date)." | his opponent row |
| 5 | streak (2: one winning, one drought) | active players whose streak runs through 2025-26: 5+ winning seasons in a row, or 4+ seasons without a playoff trip; the top 10 rotate by date | "{P}'s teams have had a winning record in each of his last {n} seasons ({a} to {b}), {the longest active streak / No. k among active players}." / "{P} has not been on a playoff team in his last {n} seasons ..." | his season-by-season table |
| 5b | mates (2: one drop, one together) | from `scripts/teammates.py`, regular season incl. the season to date. Drop: active players' pairs that qualify for "Biggest teammate swings" (100+ games together, 40+ without, z of 2.58 or more) with a teammate who made an All-Star team, biggest drop first. Together: current teammates (same team now) with 200+ games together, best win % first. Each rotates through its top 10 | "{P}'s teams are {W}–{L} ({pct}) with {Q} and {W}–{L} ({pct}) without him, {x} points lower: the biggest drop for an active player / No. {k} among active players (regular season, through {date})." / "{P} and {Q} have played {n} regular-season games together: {W}–{L} ({pct}), the best record together / No. {k} among current teammates with 200+ games (through {date})." | the pair's row on Biggest teammate swings / his "With and without his teammates" block |
| 6 | on this day (1, more to fill) | a title-winning or 60-win-pace team-season with 5+ games by this calendar date | "On this date in {season}, the {team} were {W}–{L}. They finished {W}–{L} and won the title / a {n}-win pace over 82 games." | the team's row on that season's standings |

Picking: candidates in priority order, within the caps, one fact per player (or current team) a
day, players and teams of the day's list left out (and its archive items), up to 8; if fewer than 6, more candidates in priority
order fill the strip. **Never the same fact two days running** (the exact fact text of yesterday's
set is excluded), and a streak or on-this-day fact (same player or team-season) never repeats
within 30 days (the teammate facts too, per pair). Sets are kept 60 days in `data/facts.json`.

## Comparison of the day (`scripts/picks.py`, homepage)

Pool: suggested peer pairs (same era by the peer rules: career middles within 4 seasons) where both
players have 300+ games and at least one was an All-Star, ranked by combined Accolade score; the top
120. The pool is in a fixed shuffled order and day k shows entry k mod 120, so a pair cannot come
back within 120 days (the rule is 60). 

## Player page lead (`scripts/leads.py`)

The first rule that applies writes the first sentence; sentences 2 and 3 follow.

| Rule | When | Sentence 1 | Fields |
|---|---|---|---|
| R0 | fewer than 3 completed seasons or fewer than 82 games | "Played {n} seasons for {k} teams; his teams went {W}–{L} in his games." (only sentence) | seasons, teams, record |
| R1 | 2+ titles | "His teams won {n} titles: {seasons}." | title seasons (runs collapse: "1990-91 to 1992-93") |
| R2 | 1 title | "His teams won one title, with the {season} {team}." | title season, champion's name that season |
| R3 | no title, 1+ Finals | "His teams reached the NBA Finals {once / n times} ({seasons}) without winning the title." | Finals seasons |
| R4 | no Finals, 1+ playoff trip | "His best final NBA finish was #{rank} of {teams}, with the {season} {team}." | best RNK (ties: latest), league size |
| R5 | never a playoff trip | "His teams missed the playoffs in all {n} of his seasons; the best final finish was #{rank} of {teams}, with the {season} {team}." | as R4 |

Sentence 2 (R1 to R5): "In his {G} games for {k} teams over {n} seasons they went {W}–{L} ({pct}),
{W − L} games over/under .500, with an average final finish of {avg}."

Sentence 3 (optional): the biggest one-season rise in final finish for the same franchise in two
consecutive seasons he played for it (the team he played most games for both seasons), only when
the rise is 8 places or more: "The biggest one-season rise in his career: the {team} went from
#{a} in {season 1} to #{b} in {season 2}." It reports the team's ranks, not a cause.

Counts per rule are printed by `scripts/build_site.py` on every build.

## Opponent takeaways (player page, "Record against each opponent")

Shown only when the sample supports them. Each links to its row, which opens the games.

| Takeaway | When | Template |
|---|---|---|
| Best matchup | 3+ franchises with 20+ regular-season games each | "Best regular-season record against one franchise: {W}–{L} ({pct}) against the {franchise} in {G} games." (highest win %, ties: more games) |
| Toughest matchup | same | "Toughest regular-season record against one franchise: {W}–{L} ({pct}) against the {franchise} in {G} games." (lowest win %, ties: more games) |
| Playoff rivalry | 2+ playoff series he played in against one franchise | "Most playoff series against one franchise: {n} against the {franchise}, {SW}–{SL} in series and {W}–{L} in games." |

Franchises are named as today; game lists use each team's name that season.

## Teammate help panel (player page)

- "Average help per season: {x}" with "Entering the season: {y}"; rank among 300+ game players.
- "Most of it came from: {teammate} {points} points over {n} seasons" (top 3 by same-season points).
- Similar-help sentence (5+ seasons, 3+ seasons within 25% of his median help): "In his {n} seasons with
  help between {lo} and {hi} points, his best final finish was #{r} of {N} ({season}) and his worst
  #{r} of {N} ({season})."
- 0 = no honored teammate; "+" = a teammate with 10+ shared games has no award record.

## Peer comparisons

- Suggestion: "Careers centered on {season} and {season}; help {x} and {y} points per season; own honors
  {a} and {b} per season; {g} and {g} games." Prefixed "Closest by the same rules, outside the usual
  limits." when it is a fallback match.
- Scoreboard lines (every comparison): "Less help: {A} ({x} per season vs {y})." and "Lower is better for
  finish and help. With vs without isn't counted. Team results, not who was better." The full rules
  are on comparison-rules.html ("How this works").
- Compare page, biggest single-season gap (career seasons aligned, largest difference in W − L in his
  games): "The biggest gap in one season came in career season {k}: {A}'s {season} {team} went {W}–{L}
  in his games (#{r} of {N}); {B}'s {season} {team} went {W}–{L} (#{r} of {N})."
- Share card: names, seasons span, record and win %, W − L, average finish, titles and playoff trips,
  help per season, and the scope line "Regular seasons through 2025-26. Records are his teams' in his
  games; help is Teammates Score points per season."

## Season board lead

"The {champion} finished #1 ({W}–{L}), the {runner-up} #2 ({W}–{L})." From the standings' RNK.

## Meta descriptions

Player: "{name}'s teams went {W}–{L} ({pct}) in his games, {span}: {winning} winning seasons,
{trips} playoff trips, {titles} titles, average final finish {avg}. Every season ranked, playoffs,
with and without him."

## Formats

Win rates 65.9%; gaps +26.0 pp from unrounded rates; records 706–366 (en dash); W − L with a
true minus sign; empty samples N/A; dates "Nov. 16, 2026".

## Head-to-head scoreboard links

Every row of the scoreboard (pre-built pair pages and compare/?a=&b=) is clickable. The category opens
its board with both players highlighted (`?hl=a,b`; the page scrolls to the higher-ranked one) and each
value cell opens that player's row (`?hl=<slug>#p-<slug>`): Career record -> career wins, win % sort
(400+ games); W − L -> wins minus losses; Titles; Playoff trips; Deepest run; Average finish (5+
seasons); With vs without -> career with/without (200+ played, 50+ missed); Help per season -> the
comparison rules page (no board). A player outside a board's qualifying group links to his own page.

## Arrival and departure (player page)

Built from the seasons in which he played at least one game (completed seasons plus the one in
progress), in order of appearance:
- **Debut**: his first franchise in his first season with games.
- **Arrived**: a franchise he was not with in his previous season with games (a mid-season trade
  counts in that season).
- **Left**: only when his next season with games is for a different franchise, or he never plays
  again; shown as "after {season}" with the team's record that season and the next one "without him".
- **Missed**: one or more whole seasons without a game followed by a return to the same franchise
  are one row, "Missed {seasons} (no games)", with the team's record in each of those seasons
  without him. No Left / Arrived pair.
Rows need the team's completed seasons (the season in progress has no final record yet).
