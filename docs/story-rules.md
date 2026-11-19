# Story rules: every sentence is a template

Team Success has no model-written prose. Every sentence that states a fact (player leads, daily
stories, takeaways, titles, descriptions, alt text, share text) is a template filled from data and
chosen by the rules below. A template states only what its fields prove. No template says a player
made, lifted, carried or dragged a team: it says what the record was.

## Today in Team Success (`scripts/daily_story.py`, nightly)

One story per UTC date. The nightly Action runs four times a day (11:37, 14:37, 18:37 and 23:37
UTC): the first run of a date writes that date's story; a later run rewrites it only when the
data cutoff moved (newer games), comparing with the state from before the first run; otherwise
nothing is committed. Candidates are ranked by type first, then within type; the first is the lead.
Every story shows its date and the data cutoff (last game in the nightly data).

| Priority | Type | When | Headline / body |
|---|---|---|---|
| 1 | pass | an active player's career W − L (completed seasons + this season) moved ahead of another player's in the games of the last game date (worked out from the season's game log), the games are newer than the previous story's cutoff, and he is in the top 200 | "{P} passes {Q} on the career wins-minus-losses list" / his total split into completed seasons and this season, his rank counting this season |
| 2 | matchup | tonight's schedule (cdn.nba.com) has an active player with 300+ games facing a franchise he has played 15+ regular-season games against with a win rate of .400 or lower (lowest first) | "Tonight: {P} and the {team} face the {opp}" / his record against that franchise, and "his lowest win rate against any franchise he has faced 15+ times" only when true |
| 3 | climb | an active player has moved past players on the career W − L list this season (top-100 players first, by rank; otherwise the biggest climb) | "{P} moves past {Q} on the career wins-minus-losses list" / this season's W − L, career total and rank, how many he passed; {Q} is the passed player with the highest Accolade score |
| 4 | absence | a team reached 10 wins in the games a player missed since the previous run, 8+ games each side | "The {team} reach 10 wins in the games {P} has missed" / both records with both samples |
| 5 | compare | quiet day (always available): the comparison-of-the-day pool below, the pair half a cycle away from the homepage's | "{A} and {B}: same era, similar teammate help" / both records, average finishes and help |

**No repeats.** A lead (type + players) never comes back within 30 days; the next candidate leads
instead. The compare type always has a candidate, so a day with no games still gets a new story.

**Supporting links are about the story**, never a random pair:

| Lead | Link 1 | Link 2 |
|---|---|---|
| pass, climb | {P} vs {Q} on the compare page | {Q}'s page |
| matchup | {P}'s record against every franchise | this season's with and without board |
| absence | {P}'s page | this season's standings |
| compare | {A}'s page | {B}'s page |

A five-game absence split never leads (stricter cutoff of 8 and a 10-win threshold). Permalinks
(`stories/<date>.html`) are shareable with their own image and are noindex; the archive
(`stories/index.html`) is indexed.

## Fun facts (`scripts/fun_facts.py`, nightly; homepage strip under the title)

6 to 8 one-sentence facts a day, each a template filled from data, each with a face (player) or a
team logo, each linking to the page or row that proves it. Same schedule as the story: the first
run of a UTC date writes the set, a later run rewrites it only when the data cutoff moved.

| Priority | Type (cap per day) | When | Template | Proof link |
|---|---|---|---|---|
| 1 | pass (2, one per board) | in the games of the last game date an active player moved ahead of another player on career wins or career W − L (completed seasons + this season) and is now in the top 250; the best-ranked such pass per board | "{P} passed {Q} [and n others] last night (or "on {date}" when the data is older) for No. {r} in career wins / career wins minus losses ({value} in his games)." | the board row (`?hl=` + anchor) |
| 2 | start (2) | a team with 8+ games has the best (or worst) record through that many games since a season 5+ years ago, league-wide; else the franchise's best (worst) since a season 10+ years ago, or ever (10+ earlier seasons) | "The {team} are {W}–{L}, the [franchise's] best / worst start through {n} games since the {season} {team} ({W}–{L})." | the team's row in this season's standings |
| 3 | split (2) | 10+ games played AND 8+ missed this season, and his team is unbeaten or winless in the games he played or missed | "The {team} are {W}–0 / 0–{L} in the games {P} played / missed this season." | his row on the with and without board |
| 4 | matchup (2) | tonight's schedule: an active player with 20+ regular-season games against tonight's opponent, win rate .700+ or .350 or lower (most extreme first) | "Tonight vs the {opp}: {P}'s teams are {W}–{L} ({pct}) in his {n} regular-season games against them." | his opponent row |
| 5 | streak (2: one winning, one drought) | active players whose streak runs through 2025-26: 5+ winning seasons in a row, or 4+ seasons without a playoff trip; the top 10 rotate by date | "{P}'s teams have had a winning record in each of his last {n} seasons ({a} to {b}), {the longest active streak / No. k among active players}." / "{P} has not been on a playoff team in his last {n} seasons ..." | his season-by-season table |
| 6 | on this day (1, more to fill) | a title-winning or 60-win-pace team-season with 5+ games by this calendar date | "On this date in {season}, the {team} were {W}–{L}. They finished {W}–{L} and won the title / a {n}-win pace over 82 games." | the team's row on that season's standings |

Picking: candidates in priority order, within the caps, one fact per player (or current team) a
day, players of the day's story left out, up to 8; if fewer than 6, more candidates in priority
order fill the strip. **Never the same fact two days running** (the exact fact text of yesterday's
set is excluded), and a streak or on-this-day fact (same player or team-season) never repeats
within 30 days. Sets are kept 60 days in `data/facts.json`.

## Comparison of the day (`scripts/picks.py`, homepage)

Pool: suggested peer pairs (same era by the peer rules: career middles within 4 seasons) where both
players have 300+ games and at least one was an All-Star, ranked by combined Accolade score; the top
120. The pool is in a fixed shuffled order and day k shows entry k mod 120, so a pair cannot come
back within 120 days (the rule is 60). The daily story's quiet-day pair is half a cycle away, so the
homepage and the story never show the same pair on the same day.

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
