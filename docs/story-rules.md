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
| 1 | career wins milestone | his career wins in his games (incl. 2026-27 to date) crossed 300, 400, 500 ... | `wins-mark` (below). Rank shown only when it is No. 1,000 or better. | career wins board row |
| 1 | W − L milestone | his career W − L crossed a multiple of 100 (+100, +200 ... or −100 ...) | `wl-mark-up` / `wl-mark-down` (below). A negative milestone never reads "reached −100": it says the teams are 100 games under .500 with him playing. Rank shown only when it is No. 1,000 or better and the milestone is positive. | W − L board row |
| 1 | win % top 25 | among players with 500+ games, he moved into the top 25 in career win % | `pct-top` (below) | career wins board, win % sort, 500+ games |
| 2 | notable pass (wins, W − L, win %) | the passer is in that board's top 250 (win %: top 100), AND the player passed is notable on that board: top 100 on it, a Hall of Famer (as a player, coach or contributor) or a 3+ time All-Star. Several passes for one player: only the most notable name (Hall of Famer as a player first, then most All-Star selections, then Hall of Famer as a coach or contributor, then best rank on the board) | `wins-pass` / `wl-pass` / `pct-pass` (below). 1 to 5 players passed: every one named and linked, labels kept, most notable first ("A and B"; "A, B and C"). 6 or more: the 2 most notable, then "and {n} others" (n is then 4 or more) linking to the board at the passer's row. The value never sits in parentheses right after the names. | board row |
| 3 | team start | his team played last night, 8+ games, and the record is the franchise's best (worst) through that many games since a season 10+ years ago, or ever (10+ earlier seasons) | `start-fr-since-best` / `-worst`, `start-fr-ever-best` / `-worst` (below) | the team's row in this season's standings |
| 3 | team streak | a current winning or losing streak of 5+ games that is the franchise's longest since a season 10+ years ago, or ever | `streak-win-since` / `-ever`, `streak-lose-since` / `-ever` (below) | standings row |
| 4 | with / without | his team played last night; 10+ games played and 8+ missed this season; one side unbeaten or winless, or a gap of 40+ points | `ww-with` / `ww-without` (below) | his row on the with and without board at 10 and 8 |
| 5 | tonight | an active player with 15+ regular-season games against tonight's opponent (nba-editorial-bots' schedule CSV, `data/schedule_<season>.csv` on its Pages site, read the way nba-head-to-head reads it for "Tonight's duels": games on today's US Eastern date that are not final) and a win rate of .700+ or .350 or lower | `tonight-good` (.500 or better) / `tonight-bad` (below). Counts completed seasons plus the season to date, like the opponent row the record links to. | his opponent row |

No sentence in the list or in the fun facts carries a season-scope parenthetical ("2026-27 to date",
"incl. 2026-27 to date"); a scope stays only where a number stops at an earlier season ("(2018-19 to
2025-26)" on a streak, "(through 2025-26)").

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
| 1 | pass (0: moved to the "Last night" list) | in the games of the last game date an active player moved ahead of another player on career wins or career W − L (completed seasons + this season) and is now in the top 250; the best-ranked such pass per board | `wins-pass` / `wl-pass` (below), same name rule as the list | the board row (`?hl=` + anchor) |
| 2 | start (2) | a team with 8+ games has the best (or worst) record through that many games since a season 5+ years ago, league-wide; else the franchise's best (worst) since a season 10+ years ago, or ever (10+ earlier seasons) | `start-lg-since-*`, `start-lg-ever-*`, `start-fr-since-*`, `start-fr-ever-*` (below) | the team's row in this season's standings |
| 3 | split (2) | 10+ games played AND 8+ missed this season, and his team is unbeaten or winless in the games he played or missed | `split-perfect-with` / `split-winless-with` / `split-perfect-without` / `split-winless-without` (below) | his row on the with and without board |
| 4 | matchup (2) | tonight's schedule: an active player with 20+ regular-season games against tonight's opponent (completed seasons plus the season to date), win rate .700+ or .350 or lower (most extreme first) | the list's `tonight-good` / `tonight-bad` (below) | his opponent row |
| 5 | streak (2: one winning, one drought) | active players whose streak runs through 2025-26: 5+ winning seasons in a row, or 4+ seasons without a playoff trip; the top 10 rotate by date | `career-winning` / `career-drought` (below) | his season-by-season table |
| 5b | mates (2: one drop, one together) | from `scripts/teammates.py`, regular season incl. the season to date. Drop: active players' pairs that qualify for "Biggest teammate swings" (100+ games together, 40+ without, z of 2.58 or more) with a teammate who made an All-Star team, biggest drop first. Together: current teammates (same team now) with 200+ games together, best win % first. Each rotates through its top 10 | `mates-drop` / `mates-together` (below) | the pair's row on Biggest teammate swings / his "With and without his teammates" block |
| 6 | on this day (1, more to fill) | a title-winning or 60-win-pace team-season with 5+ games by this calendar date | `archive-title` / `archive-pace` (below, also the list's "From the archive" items) | the team's row on that season's standings |

Picking: candidates in priority order, within the caps, one fact per player (or current team) a
day, players and teams of the latest "Last night" list left out (the list shown above the strip, even
when it is from the day before; its archive items too), up to 8; if fewer than 6, more candidates in priority
order fill the strip. **Never the same fact two days running** (yesterday's facts are excluded by their data, the
slots a template is filled with, so a new wording of the same fact still counts as a repeat; sets
written before Nov. 26, 2026 were keyed by their text, a one-time change), and a streak or on-this-day fact (same player or team-season) never repeats
within 30 days (the teammate facts too, per pair). Sets are kept 60 days in `data/facts.json`, each with the list it was checked against
(`against`: that list's date and cutoff); when that list is regenerated, the next run rebuilds the set.

## Sentence templates (`scripts/phrasing.py`)

Every item of the "Last night" list and every fun fact is one sentence from a set of 7 to 8
templates per type, all with the same data and the same links: the player's name links to his page, a
number or rank to the board row, a record to the games. The template is picked from a hash of (date,
type, subject id), so a rerun of the same date gives the same sentence, and never repeats inside one
list or one strip (a repeat steps to the next template of the set). Picking the template happens after
the items are chosen and never changes which items are chosen. `[[...]]` is a piece left out when its
value is missing (a rank worse than No. 1,000, or any negative milestone). `{Team}` / `{team}`,
`{Tm}` / `{tm}` and `{Opp}` / `{opp}` are the same link with a capital or lowercase "The". No template
says "to date", "on the board" or "his games", and none uses a dash for punctuation (checked by
`tests/test_phrasing.py`, which also checks that this section lists every template). Lists written
before Nov. 26, 2026 keep their wording.

**`wins-mark`** (links: {P}, {M})

1. {P} reached {M} career wins[[, which puts him {rank} all-time]].
1. {P} has now been part of {M} wins[[, good for {rank} all-time]].
1. Win No. {M} for {P}.[[ He's {rank} on the all-time list.]]
1. With last night's win, {P}'s teams have {M} wins with him playing.[[ That's {rank} all-time.]]
1. {P} hit {M} career wins last night[[ and sits {rank} all-time]].
1. Add {P} to the {M}-win club.[[ He ranks {rank} all-time.]]
1. {P}'s teams have now won {M} games with him on the floor[[, {rank} all-time]].
1. Another milestone for {P}, who now has {M} career wins[[, which ranks {rank} all-time]].

**`wl-mark-up`** (links: {P}, {M})

1. {P}'s teams are now {M} games over .500 with him playing[[, {rank} all-time]].
1. {P} reached {M} games over .500 for his career[[, which ranks {rank} all-time]].
1. Make it {M} games over .500 for {P}'s teams with him on the floor.[[ That's {rank} all-time.]]
1. With last night's win, {P}'s career record is {M} games over .500[[, good for {rank} all-time]].
1. {P}'s teams have won {M} more games than they've lost with him playing[[, which puts him {rank} all-time]].
1. Count {P} among the players {M} games over .500 for a career.[[ He's {rank} all-time.]]
1. {P} crossed {M} games over .500 for his career[[ and ranks {rank} all-time]].
1. Another round number for {P}, whose teams are {M} games over .500 with him playing[[, {rank} all-time]].

**`wl-mark-down`** (links: {P}, {M})

1. {P}'s teams are now {M} games under .500 with him playing.
1. {P}'s career record with him on the floor has slipped to {M} games under .500.
1. {P}'s teams have now lost {M} more games than they've won with him playing.
1. A rough mark for {P}, whose teams are {M} games under .500 in his career.
1. {P} is now {M} games under .500 for his career.
1. {P}'s teams fell to {M} games under .500 with him in the lineup.
1. Tough going for {P}'s teams, now {M} games under .500 with him playing.
1. Last night's loss left {P}'s teams {M} games under .500 for his career.

**`wins-pass`** (links: {P}, {names}, {rank})

1. {P} passed {names} and is now {rank} in career wins ({val}).
1. {P} moved past {names} into {rank} in career wins ({val}).
1. {P} climbed past {names} on the career wins list. He's now {rank} with {val}.
1. With {val} career wins, {P} is now ahead of {names} at {rank} all-time.
1. {P} is up to {rank} in career wins with {val}, after passing {names}.
1. Last night's win moved {P} ahead of {names}. He's {rank} in career wins with {val}.
1. {P} now has more career wins than {names}, {val} in all, good for {rank}.
1. {P} jumped {names} and now sits {rank} in career wins with {val}.

**`wl-pass`** (links: {P}, {names}, {rank})

1. {P} passed {names} and is now {rank} in career wins minus losses ({val}).
1. {P} moved past {names} into {rank} in career wins minus losses ({val}).
1. {P}'s teams are now {val} with him playing, which moves him past {names} to {rank} all-time.
1. {P} climbed past {names} on the wins-minus-losses list. He's {rank} at {val}.
1. At {val}, {P} now ranks ahead of {names} in career wins minus losses, at {rank}.
1. {P} is up to {rank} in career wins minus losses at {val}, after passing {names}.
1. Last night's win moved {P} ahead of {names}. He's {rank} in wins minus losses at {val}.
1. {P} now sits {rank} in career wins minus losses at {val}, ahead of {names}.

**`pct-top`** (links: {P}, {rank})

1. {P} moved into the top 25 in career win % at {pct}. He's {rank} among players with {mins}+ games.
1. {P}'s teams have won {pct} of the games he's played, good for {rank} among players with {mins}+ games.
1. {P} joined the top 25 in career win % at {pct}, {rank} among players with {mins}+ games.
1. {P} cracked the top 25 in career win % ({pct}). Among players with {mins}+ games, he's {rank}.
1. At {pct}, {P} now ranks {rank} in career win % among players with {mins}+ games.
1. {P} is now {rank} in career win % among players with {mins}+ games, winning {pct} of the time.
1. Few players win as often as {P}, whose teams win {pct} with him playing. He's {rank} among players with {mins}+ games.
1. {P}'s {pct} career win rate is now {rank} among players with {mins}+ games, inside the top 25.

**`pct-pass`** (links: {P}, {names}, {rank})

1. {P}'s {pct} career win rate now tops {names}. He's {rank} among players with {mins}+ games.
1. {P} passed {names} in career win % and is now at {pct}, {rank} among players with {mins}+ games.
1. {P} moved past {names} in career win %. At {pct}, he's {rank} among players with {mins}+ games.
1. With a {pct} career win rate, {P} is now ahead of {names}, {rank} among players with {mins}+ games.
1. {P} now has a better career win rate than {names} at {pct}, which is {rank} among players with {mins}+ games.
1. {P} is up to {rank} in career win % among players with {mins}+ games at {pct}, after passing {names}.
1. Last night moved {P} past {names} in career win %. He's at {pct}, {rank} among players with {mins}+ games.
1. {P} climbed to {rank} in career win % ({pct}) among players with {mins}+ games, ahead of {names}.

**`start-fr-since-best`** (links: {team}, {then})

1. {Team} are {rec}, their best start through {n} games since {then} ({then_rec}).
1. {Team} haven't started this well since {then}, when they were {then_rec} through {n} games. This year they're {rec}.
1. At {rec}, {team} have their best {n}-game start since {then} ({then_rec}).
1. {Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) to find a start this good.
1. {Team} are off to a {rec} start, the franchise's best through {n} games since {then} ({then_rec}).
1. Through {n} games, {team} are {rec}. The last time they started this well was {then} ({then_rec}).
1. It's been a while since {team} looked this good. They're {rec} through {n} games, their best start since {then} ({then_rec}).
1. {Team} keep rolling at {rec}, their best mark after {n} games since {then} ({then_rec}).

**`start-fr-since-worst`** (links: {team}, {then})

1. {Team} are {rec}, their worst start through {n} games since {then} ({then_rec}).
1. {Team} haven't started this badly since {then}, when they were {then_rec} through {n} games. This year they're {rec}.
1. At {rec}, {team} have their worst {n}-game start since {then} ({then_rec}).
1. {Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) to find a start this rough.
1. {Team} are off to a {rec} start, the franchise's worst through {n} games since {then} ({then_rec}).
1. Through {n} games, {team} are {rec}. The last time they started this poorly was {then} ({then_rec}).
1. It's been a rough start for {team}, who are {rec} through {n} games, their worst since {then} ({then_rec}).
1. {Team} sit at {rec}, a start they haven't seen through {n} games since {then} ({then_rec}).

**`start-fr-ever-best`** (links: {team})

1. {Team} are {rec}, the best start through {n} games in their {k} seasons.
1. In {k} seasons, {team} have never been better through {n} games. They're {rec}.
1. At {rec}, {team} are off to the best {n}-game start in franchise history ({k} seasons).
1. {Team} are {rec} through {n} games, a franchise record in {k} seasons.
1. This is the best start {team} have ever had. They're {rec} through {n} games, tops in {k} seasons.
1. Through {n} games, {team} are {rec}, better than any start in their {k} seasons.
1. {Team} keep making history at {rec}, the best mark through {n} games in their {k} seasons.
1. Franchise history for {team}, who are {rec} through {n} games, their best start in {k} seasons.

**`start-fr-ever-worst`** (links: {team})

1. {Team} are {rec}, the worst start through {n} games in their {k} seasons.
1. In {k} seasons, {team} have never been worse through {n} games. They're {rec}.
1. At {rec}, {team} are off to the worst {n}-game start in franchise history ({k} seasons).
1. {Team} are {rec} through {n} games, a franchise low in {k} seasons.
1. This is the worst start {team} have ever had. They're {rec} through {n} games, the low point in {k} seasons.
1. Through {n} games, {team} are {rec}, worse than any start in their {k} seasons.
1. {Team} have never been here before. They're {rec} through {n} games, their worst start in {k} seasons.
1. A franchise low for {team}, who are {rec} through {n} games, their worst start in {k} seasons.

**`start-lg-since-best`** (links: {team}, {then})

1. {Team} are {rec}, the best start through {n} games by any team since {then} ({then_rec}).
1. No team has started better through {n} games since {then} ({then_rec}). {Team} are {rec}.
1. At {rec}, {team} have the best {n}-game start in the NBA since {then} ({then_rec}).
1. {Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) for a start this good.
1. {Team} are off to a {rec} start, the league's best through {n} games since {then} ({then_rec}).
1. Through {n} games, {team} are {rec}. The last team to start this well was {then} ({then_rec}).
1. It's been a while since any team looked this good. {Team} are {rec} through {n} games, the best since {then} ({then_rec}).
1. {Team} sit at {rec}, a start no team has topped through {n} games since {then} ({then_rec}).

**`start-lg-since-worst`** (links: {team}, {then})

1. {Team} are {rec}, the worst start through {n} games by any team since {then} ({then_rec}).
1. No team has started worse through {n} games since {then} ({then_rec}). {Team} are {rec}.
1. At {rec}, {team} have the worst {n}-game start in the NBA since {then} ({then_rec}).
1. {Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) for a start this rough.
1. {Team} are off to a {rec} start, the league's worst through {n} games since {then} ({then_rec}).
1. Through {n} games, {team} are {rec}. The last team to start this poorly was {then} ({then_rec}).
1. It's been a while since any team started this badly. {Team} are {rec} through {n} games, the worst since {then} ({then_rec}).
1. {Team} sit at {rec}, a start no team has fallen below through {n} games since {then} ({then_rec}).

**`start-lg-ever-best`** (links: {team})

1. {Team} are {rec}, the best record through {n} games of any NBA team since 1946-47.
1. No NBA team has ever been better through {n} games. {Team} are {rec}.
1. At {rec}, {team} have the best {n}-game start in NBA history.
1. {Team} are {rec} through {n} games, an NBA record since 1946-47.
1. Nobody has started like this. {Team} are {rec} through {n} games, the best ever.
1. Through {n} games, {team} are {rec}, better than any team in league history.
1. {Team} are making history at {rec}, the best mark through {n} games of any team ever.
1. The best start through {n} games in NBA history belongs to {team}, now {rec}.

**`start-lg-ever-worst`** (links: {team})

1. {Team} are {rec}, the worst record through {n} games of any NBA team since 1946-47.
1. No NBA team has ever been worse through {n} games. {Team} are {rec}.
1. At {rec}, {team} have the worst {n}-game start in NBA history.
1. {Team} are {rec} through {n} games, an NBA low since 1946-47.
1. Nobody has started like this. {Team} are {rec} through {n} games, the worst ever.
1. Through {n} games, {team} are {rec}, worse than any team in league history.
1. {Team} are in uncharted territory at {rec}, the worst mark through {n} games of any team ever.
1. The worst start through {n} games in NBA history belongs to {team}, now {rec}.

**`streak-win-ever`** (links: {team})

1. {Team} have won {k} in a row, the longest streak in their {S} seasons.
1. {Team} are on a {k}-game winning streak, a franchise record in {S} seasons.
1. That's {k} straight wins for {team}, the longest run in franchise history ({S} seasons).
1. {Team} keep winning. It's {k} in a row now, longer than any streak in their {S} seasons.
1. Never before in {S} seasons have {team} won {k} straight. They have now.
1. {Team} haven't lost in {k} games, their longest winning streak ever ({S} seasons).
1. A franchise record for {team}, who have won {k} in a row, the best in {S} seasons.
1. Make it {k} straight for {team}, the longest winning streak in their {S} seasons.

**`streak-win-since`** (links: {team})

1. {Team} have won {k} in a row, their longest streak since {then}.
1. {Team} are on a {k}-game winning streak, the franchise's longest since {then}.
1. That's {k} straight wins for {team}, their best run since {then}.
1. {Team} keep winning. It's {k} in a row now, their longest streak since {then}.
1. The last time {team} won this many in a row was {then}. They're at {k} straight.
1. {Team} haven't lost in {k} games, their longest winning streak since {then}.
1. {Team} have stacked up {k} straight wins, the most in a row since {then}.
1. Make it {k} straight for {team}, their longest winning streak since {then}.

**`streak-lose-ever`** (links: {team})

1. {Team} have lost {k} in a row, the longest skid in their {S} seasons.
1. {Team} are on a {k}-game losing streak, a franchise record in {S} seasons.
1. That's {k} straight losses for {team}, the longest run in franchise history ({S} seasons).
1. {Team} keep losing. It's {k} in a row now, longer than any skid in their {S} seasons.
1. Never before in {S} seasons have {team} lost {k} straight.
1. {Team} haven't won in {k} games, their longest losing streak ever ({S} seasons).
1. A franchise low for {team}, who have dropped {k} in a row, the worst in {S} seasons.
1. Make it {k} straight losses for {team}, the longest losing streak in their {S} seasons.

**`streak-lose-since`** (links: {team})

1. {Team} have lost {k} in a row, their longest skid since {then}.
1. {Team} are on a {k}-game losing streak, the franchise's longest since {then}.
1. That's {k} straight losses for {team}, their worst run since {then}.
1. {Team} keep losing. It's {k} in a row now, their longest skid since {then}.
1. The last time {team} lost this many in a row was {then}. They're at {k} straight.
1. {Team} haven't won in {k} games, their longest losing streak since {then}.
1. {Team} have dropped {k} straight, the most in a row since {then}.
1. Make it {k} straight losses for {team}, their longest losing streak since {then}.

**`ww-with`** (links: {P}, {wo})

1. {Tm} are {wo} without {P} and {w} with him ({g} played, {m} missed).
1. {Tm} are {w} when {P} plays and {wo} when he doesn't ({g} played, {m} missed).
1. The split for {tm} with {P} this season is {w}, against {wo} without him ({g} played, {m} missed).
1. With {P}, {tm} are {w}. Without him, {wo} ({g} played, {m} missed).
1. {Tm} have gone {w} in the {g} games {P} has played and {wo} in the {m} he's missed.
1. Big gap for {tm}, who are {w} with {P} and {wo} without him ({g} played, {m} missed).
1. When {P} sits, {tm} are {wo}. When he plays, {w} ({g} played, {m} missed).
1. {Tm} look like a different team with {P}, {w} with him and {wo} without ({g} played, {m} missed).

**`ww-without`** (links: {P}, {wo})

1. {Tm} are {wo} without {P} and {w} with him ({g} played, {m} missed).
1. {Tm} are {w} when {P} plays and {wo} when he doesn't ({g} played, {m} missed).
1. An odd split for {tm}, who are {wo} without {P} and {w} with him ({g} played, {m} missed).
1. Without {P}, {tm} are {wo}. With him, {w} ({g} played, {m} missed).
1. {Tm} have gone {wo} in the {m} games {P} has missed and {w} in the {g} he's played.
1. Strange but true, {tm} are {wo} without {P} and {w} with him ({g} played, {m} missed).
1. When {P} sits, {tm} are {wo}. When he plays, {w} ({g} played, {m} missed).
1. {Tm} have the better record without {P} this season, {wo} to {w} ({m} missed, {g} played).

**`tonight-good`** (links: {P}, {rec})

1. {P} faces {opp} tonight. His teams are {rec} against them, {a} {pct} win rate.
1. {P}'s teams are {rec} against {opp}, who they play tonight.
1. {P} has owned {opp}, going {rec} in his career. They meet again tonight.
1. Good sign for {P} tonight. His teams are {rec} against {opp}.
1. {P} gets {opp} tonight, a team his teams have beaten {rec} over the years.
1. Tonight {P} sees {opp} again. His teams have won {pct} of those games ({rec}).
1. History favors {P} tonight against {opp}, with his teams at {rec} in the regular season.
1. {Opp} have been a good matchup for {P}. His teams are {rec} against them, and they play tonight.

**`tonight-bad`** (links: {P}, {rec})

1. {P} faces {opp} tonight. His teams are {rec} against them, {a} {pct} win rate.
1. Tough matchup for {P} tonight. His teams have gone {rec} against {opp}.
1. {P}'s teams are just {rec} against {opp}, who they play tonight.
1. {Opp} have had {P}'s number, {rec} against his teams. They meet again tonight.
1. {P} gets {opp} tonight. His teams have won only {pct} of those games ({rec}).
1. History isn't on {P}'s side tonight against {opp}, with his teams at {rec} in the regular season.
1. Tonight {P} sees {opp} again, a team his teams are {rec} against.
1. {P}'s teams have struggled against {opp}, going {rec}. They play tonight.

**`archive-title`** (links: {team})

1. On this date in {season}, the {team} were {rec}. They finished {final} and won the title.
1. The {season} {team} were {rec} on this date. They went on to finish {final} and win the championship.
1. This date in {season} found the {team} at {rec}. They finished {final} and won the title.
1. Remember the {season} {team}? On this date they were {rec}, on the way to a {final} finish and a title.
1. On this date in {season}, the eventual champion {team} stood at {rec}. They finished {final}.
1. The {team} were {rec} on this date in {season} and finished {final} with a championship.
1. Looking back to {season}, the {team} were {rec} on this date. They ended at {final} and won the title.
1. A title team on this date in {season}, the {team} were {rec} and finished {final}.

**`archive-pace`** (links: {team})

1. On this date in {season}, the {team} were {rec}. They finished {final}, {ap} {pace}-win pace over 82 games.
1. The {season} {team} were {rec} on this date. They finished {final}, {ap} {pace}-win pace over 82 games.
1. This date in {season} found the {team} at {rec}. They finished {final}, good for {ap} {pace}-win pace.
1. Remember the {season} {team}? On this date they were {rec}, on the way to {final}, {ap} {pace}-win pace.
1. On this date in {season}, the {team} stood at {rec}. They ended at {final}, {ap} {pace}-win pace over 82 games.
1. The {team} were {rec} on this date in {season} and finished {final}, {ap} {pace}-win pace.
1. Looking back to {season}, the {team} were {rec} on this date. They finished {final}, {ap} {pace}-win pace over 82 games.
1. {AP} {pace}-win pace team, the {season} {team} were {rec} on this date and finished {final}.

**`split-perfect-with`** (links: {P})

1. {Tm} are {rec} in the games {P} has played this season.
1. {Tm} haven't lost with {P} in the lineup this season, {rec} in his {n} games.
1. Perfect so far with {P}. {Tm} are {rec} when he plays.
1. {P} has played {n} games for {tm} this season, and they've won all of them ({rec}).
1. When {P} plays, {tm} win. They're {rec} with him this season.
1. {Tm} are unbeaten with {P} on the floor this season ({rec}).
1. Still no losses for {tm} with {P} playing, {rec} this season.
1. It's {rec} for {tm} in the games {P} has played this season, still perfect.

**`split-winless-with`** (links: {P})

1. {Tm} are {rec} in the games {P} has played this season.
1. {Tm} haven't won with {P} in the lineup this season, {rec} in his {n} games.
1. No wins yet for {tm} with {P} playing. They're {rec} with him.
1. {P} has played {n} games for {tm} this season, and they've lost all of them ({rec}).
1. {Tm} are still looking for a win with {P} on the floor ({rec}).
1. {Tm} are winless in {P}'s {n} games this season ({rec}).
1. A tough run for {P}, with {tm} {rec} in the games he's played this season.
1. It's {rec} for {tm} in the games {P} has played this season.

**`split-perfect-without`** (links: {P})

1. {Tm} are {rec} in the games {P} has missed this season.
1. {Tm} haven't lost without {P} this season, {rec} in the {n} games he's missed.
1. Perfect so far without {P}. {Tm} are {rec} when he sits.
1. {P} has missed {n} games for {tm} this season, and they've won all of them ({rec}).
1. {Tm} are unbeaten in the games {P} has missed this season ({rec}).
1. Still no losses for {tm} when {P} sits out, {rec} this season.
1. When {P} sits, {tm} are {rec} this season.
1. It's {rec} for {tm} in the games {P} has missed this season, still perfect.

**`split-winless-without`** (links: {P})

1. {Tm} are {rec} in the games {P} has missed this season.
1. {Tm} haven't won without {P} this season, {rec} in the {n} games he's missed.
1. No wins yet for {tm} when {P} sits. They're {rec}.
1. {P} has missed {n} games for {tm} this season, and they've lost all of them ({rec}).
1. {Tm} are still looking for a win without {P} ({rec}).
1. {Tm} are winless in the {n} games {P} has missed this season ({rec}).
1. When {P} sits, {tm} are {rec} this season.
1. It's {rec} for {tm} in the games {P} has missed this season.

**`career-winning`** (links: {P}, {n})

1. {P}'s teams have had a winning record in each of his last {n} ({span}), {tag}.
1. {P} has been on a winning team {n} straight ({span}), {tag}.
1. Winning is a habit for {P}, whose teams have finished above .500 in each of his last {n} ({span}). That's {tag}.
1. {P} hasn't played for a losing team in his last {n} ({span}), {tag}.
1. Every one of {P}'s last {n} has ended with a winning record ({span}), {tag}.
1. {P}'s run of winning seasons is up to {n} ({span}), {tag}.
1. Going back {n} ({span}), {P}'s teams have finished above .500 every time. That's {tag}.
1. {P} keeps landing on winners, {n} in a row ({span}), {tag}.

**`career-drought`** (links: {P}, {n})

1. {P} has not been on a playoff team in his last {n} ({span}), {tag}.
1. {P}'s playoff drought is up to {n} ({span}), {tag}.
1. It's been {n} since {P} played for a playoff team ({span}). That's {tag}.
1. {P}'s teams have missed the playoffs in each of his last {n} ({span}), {tag}.
1. No playoffs for {P} in his last {n} ({span}), {tag}.
1. Going back {n} ({span}), {P} hasn't reached the playoffs. That's {tag}.
1. {P} is still waiting for a playoff trip, now {n} without one ({span}), {tag}.
1. Every one of {P}'s last {n} has ended without a playoff trip ({span}), {tag}.

**`mates-drop`** (links: {P}, {Q}, {tag})

1. {P}'s teams are {t} ({tp}) with {Q} and {o} ({op}) without him, {gap} points lower. That's {tag}.
1. {P} wins a lot more with {Q} around. His teams are {t} with him and {o} without, a {gap}-point drop, {tag}.
1. With {Q}, {P}'s teams win {tp} of the time. Without him, {op}. That {gap}-point gap is {tag}.
1. Take {Q} away and {P}'s teams drop from {tp} to {op}, {gap} points, {tag}.
1. {P}'s teams are {gap} points worse without {Q} ({t} with, {o} without), {tag}.
1. Few drops are as steep as this one. {P}'s teams are {t} with {Q} and {o} without him, {tag}.
1. {P}'s record with {Q} is {t}. Without him it's {o}, a {gap}-point difference and {tag}.
1. {P} has won {tp} of the games he's played alongside {Q} and {op} without him, {tag}.

**`mates-together`** (links: {P}, {Q}, {rec})

1. {P} and {Q} have played {n} games together and gone {rec}, {tag}.
1. {P} and {Q} keep winning together. They're {rec} in {n} games, {tag}.
1. In {n} games side by side, {P} and {Q} are {rec}. That's {tag}.
1. When {P} and {Q} both play, their teams are {rec} in {n} games, {tag}.
1. {P} and {Q} make a winning pair, {rec} in {n} games together, {tag}.
1. Few teammates win like {P} and {Q}, who are {rec} in {n} games together. That's {tag}.
1. {P} and {Q} are {rec} in their {n} games as teammates, {tag}.
1. Put {P} and {Q} together and their teams are {rec} over {n} games, {tag}.

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
