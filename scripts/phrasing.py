# (c) 2026 HoopsMatic. All rights reserved.
# Team Success sentence templates for the "Last night" list and the fun facts. Fingerprint: hm-ts-7f3a91c2-phrasing
"""Every sentence in the list and the strip is one of these templates filled from data. No model text.

A template is text with {slots}. A slot is filled with plain text (str), one link part
([text, href, bold]) or several parts ([[...], [...]], e.g. a list of linked names). [[ ... ]] marks an
optional piece: it is left out when any slot inside it is missing (None), e.g. a rank worse than
No. 1,000. Each set has 7 or 8 templates with different sentence shapes; pick() chooses one from a hash
of (date, set, subject), so a rebuild gives the same sentence, and steps past templates already used in
the same list or strip. Links stay on the words they cover: a player's name on his page, a rank or
milestone on the board row, a record on the games. Records are team records, never what a player caused.

Slots by set (see docs/story-rules.md for the rules that choose an item):
  P player link, Q second player link, names linked names (passes), rank board-row link ("No. 81"),
  M milestone link, val / pct / rec text values, Team / team team link with "The" / "the",
  Tm / tm team text with "The" / "the", then earlier-season link, then_rec, n, k, S counts,
  opp / Opp opponent text, a article for pct, season, final, pace, ap article for pace, span, tag.
"""
import hashlib
import re

SETS = {
    # ---- career wins milestone (rank left out when worse than No. 1,000) ------------------------
    "wins-mark": [
        "{P} reached {M} career wins[[, which puts him {rank} all-time]].",
        "{P} has now been part of {M} wins[[, good for {rank} all-time]].",
        "Win No. {M} for {P}.[[ He's {rank} on the all-time list.]]",
        "With last night's win, {P}'s teams have {M} wins with him playing.[[ That's {rank} all-time.]]",
        "{P} hit {M} career wins last night[[ and sits {rank} all-time]].",
        "Add {P} to the {M}-win club.[[ He ranks {rank} all-time.]]",
        "{P}'s teams have now won {M} games with him on the floor[[, {rank} all-time]].",
        "Another milestone for {P}, who now has {M} career wins[[, which ranks {rank} all-time]].",
    ],
    "wl-mark-up": [
        "{P}'s teams are now {M} games over .500 with him playing[[, {rank} all-time]].",
        "{P} reached {M} games over .500 for his career[[, which ranks {rank} all-time]].",
        "Make it {M} games over .500 for {P}'s teams with him on the floor.[[ That's {rank} all-time.]]",
        "With last night's win, {P}'s career record is {M} games over .500[[, good for {rank} all-time]].",
        "{P}'s teams have won {M} more games than they've lost with him playing[[, which puts him {rank} all-time]].",
        "Count {P} among the players {M} games over .500 for a career.[[ He's {rank} all-time.]]",
        "{P} crossed {M} games over .500 for his career[[ and ranks {rank} all-time]].",
        "Another round number for {P}, whose teams are {M} games over .500 with him playing[[, {rank} all-time]].",
    ],
    "wl-mark-down": [
        "{P}'s teams are now {M} games under .500 with him playing.",
        "{P}'s career record with him on the floor has slipped to {M} games under .500.",
        "{P}'s teams have now lost {M} more games than they've won with him playing.",
        "A rough mark for {P}, whose teams are {M} games under .500 in his career.",
        "{P} is now {M} games under .500 for his career.",
        "{P}'s teams fell to {M} games under .500 with him in the lineup.",
        "Tough going for {P}'s teams, now {M} games under .500 with him playing.",
        "Last night's loss left {P}'s teams {M} games under .500 for his career.",
    ],
    # ---- passed someone (names: every player passed, linked, labels kept) --------------------------
    "wins-pass": [
        "{P} passed {names} and is now {rank} in career wins ({val}).",
        "{P} moved past {names} into {rank} in career wins ({val}).",
        "{P} climbed past {names} on the career wins list. He's now {rank} with {val}.",
        "With {val} career wins, {P} is now ahead of {names} at {rank} all-time.",
        "{P} is up to {rank} in career wins with {val}, after passing {names}.",
        "Last night's win moved {P} ahead of {names}. He's {rank} in career wins with {val}.",
        "{P} now has more career wins than {names}, {val} in all, good for {rank}.",
        "{P} jumped {names} and now sits {rank} in career wins with {val}.",
    ],
    "wl-pass": [
        "{P} passed {names} and is now {rank} in career wins minus losses ({val}).",
        "{P} moved past {names} into {rank} in career wins minus losses ({val}).",
        "{P}'s teams are now {val} with him playing, which moves him past {names} to {rank} all-time.",
        "{P} climbed past {names} on the wins-minus-losses list. He's {rank} at {val}.",
        "At {val}, {P} now ranks ahead of {names} in career wins minus losses, at {rank}.",
        "{P} is up to {rank} in career wins minus losses at {val}, after passing {names}.",
        "Last night's win moved {P} ahead of {names}. He's {rank} in wins minus losses at {val}.",
        "{P} now sits {rank} in career wins minus losses at {val}, ahead of {names}.",
    ],
    # ---- career win %, 500+ games --------------------------------------------------------------------
    "pct-top": [
        "{P} moved into the top 25 in career win % at {pct}. He's {rank} among players with {mins}+ games.",
        "{P}'s teams have won {pct} of the games he's played, good for {rank} among players with {mins}+ games.",
        "{P} joined the top 25 in career win % at {pct}, {rank} among players with {mins}+ games.",
        "{P} cracked the top 25 in career win % ({pct}). Among players with {mins}+ games, he's {rank}.",
        "At {pct}, {P} now ranks {rank} in career win % among players with {mins}+ games.",
        "{P} is now {rank} in career win % among players with {mins}+ games, winning {pct} of the time.",
        "Few players win as often as {P}, whose teams win {pct} with him playing. He's {rank} among players with {mins}+ games.",
        "{P}'s {pct} career win rate is now {rank} among players with {mins}+ games, inside the top 25.",
    ],
    "pct-pass": [
        "{P}'s {pct} career win rate now tops {names}. He's {rank} among players with {mins}+ games.",
        "{P} passed {names} in career win % and is now at {pct}, {rank} among players with {mins}+ games.",
        "{P} moved past {names} in career win %. At {pct}, he's {rank} among players with {mins}+ games.",
        "With a {pct} career win rate, {P} is now ahead of {names}, {rank} among players with {mins}+ games.",
        "{P} now has a better career win rate than {names} at {pct}, which is {rank} among players with {mins}+ games.",
        "{P} is up to {rank} in career win % among players with {mins}+ games at {pct}, after passing {names}.",
        "Last night moved {P} past {names} in career win %. He's at {pct}, {rank} among players with {mins}+ games.",
        "{P} climbed to {rank} in career win % ({pct}) among players with {mins}+ games, ahead of {names}.",
    ],
    # ---- team starts (franchise / league; since a season / ever) ---------------------------------------
    "start-fr-since-best": [
        "{Team} are {rec}, their best start through {n} games since {then} ({then_rec}).",
        "{Team} haven't started this well since {then}, when they were {then_rec} through {n} games. This year they're {rec}.",
        "At {rec}, {team} have their best {n}-game start since {then} ({then_rec}).",
        "{Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) to find a start this good.",
        "{Team} are off to a {rec} start, the franchise's best through {n} games since {then} ({then_rec}).",
        "Through {n} games, {team} are {rec}. The last time they started this well was {then} ({then_rec}).",
        "It's been a while since {team} looked this good. They're {rec} through {n} games, their best start since {then} ({then_rec}).",
        "{Team} keep rolling at {rec}, their best mark after {n} games since {then} ({then_rec}).",
    ],
    "start-fr-since-worst": [
        "{Team} are {rec}, their worst start through {n} games since {then} ({then_rec}).",
        "{Team} haven't started this badly since {then}, when they were {then_rec} through {n} games. This year they're {rec}.",
        "At {rec}, {team} have their worst {n}-game start since {then} ({then_rec}).",
        "{Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) to find a start this rough.",
        "{Team} are off to a {rec} start, the franchise's worst through {n} games since {then} ({then_rec}).",
        "Through {n} games, {team} are {rec}. The last time they started this poorly was {then} ({then_rec}).",
        "It's been a rough start for {team}, who are {rec} through {n} games, their worst since {then} ({then_rec}).",
        "{Team} sit at {rec}, a start they haven't seen through {n} games since {then} ({then_rec}).",
    ],
    "start-fr-ever-best": [
        "{Team} are {rec}, the best start through {n} games in their {k} seasons.",
        "In {k} seasons, {team} have never been better through {n} games. They're {rec}.",
        "At {rec}, {team} are off to the best {n}-game start in franchise history ({k} seasons).",
        "{Team} are {rec} through {n} games, a franchise record in {k} seasons.",
        "This is the best start {team} have ever had. They're {rec} through {n} games, tops in {k} seasons.",
        "Through {n} games, {team} are {rec}, better than any start in their {k} seasons.",
        "{Team} keep making history at {rec}, the best mark through {n} games in their {k} seasons.",
        "Franchise history for {team}, who are {rec} through {n} games, their best start in {k} seasons.",
    ],
    "start-fr-ever-worst": [
        "{Team} are {rec}, the worst start through {n} games in their {k} seasons.",
        "In {k} seasons, {team} have never been worse through {n} games. They're {rec}.",
        "At {rec}, {team} are off to the worst {n}-game start in franchise history ({k} seasons).",
        "{Team} are {rec} through {n} games, a franchise low in {k} seasons.",
        "This is the worst start {team} have ever had. They're {rec} through {n} games, the low point in {k} seasons.",
        "Through {n} games, {team} are {rec}, worse than any start in their {k} seasons.",
        "{Team} have never been here before. They're {rec} through {n} games, their worst start in {k} seasons.",
        "A franchise low for {team}, who are {rec} through {n} games, their worst start in {k} seasons.",
    ],
    "start-lg-since-best": [
        "{Team} are {rec}, the best start through {n} games by any team since {then} ({then_rec}).",
        "No team has started better through {n} games since {then} ({then_rec}). {Team} are {rec}.",
        "At {rec}, {team} have the best {n}-game start in the NBA since {then} ({then_rec}).",
        "{Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) for a start this good.",
        "{Team} are off to a {rec} start, the league's best through {n} games since {then} ({then_rec}).",
        "Through {n} games, {team} are {rec}. The last team to start this well was {then} ({then_rec}).",
        "It's been a while since any team looked this good. {Team} are {rec} through {n} games, the best since {then} ({then_rec}).",
        "{Team} sit at {rec}, a start no team has topped through {n} games since {then} ({then_rec}).",
    ],
    "start-lg-since-worst": [
        "{Team} are {rec}, the worst start through {n} games by any team since {then} ({then_rec}).",
        "No team has started worse through {n} games since {then} ({then_rec}). {Team} are {rec}.",
        "At {rec}, {team} have the worst {n}-game start in the NBA since {then} ({then_rec}).",
        "{Team} are {rec} through {n} games. You have to go back to {then} ({then_rec}) for a start this rough.",
        "{Team} are off to a {rec} start, the league's worst through {n} games since {then} ({then_rec}).",
        "Through {n} games, {team} are {rec}. The last team to start this poorly was {then} ({then_rec}).",
        "It's been a while since any team started this badly. {Team} are {rec} through {n} games, the worst since {then} ({then_rec}).",
        "{Team} sit at {rec}, a start no team has fallen below through {n} games since {then} ({then_rec}).",
    ],
    "start-lg-ever-best": [
        "{Team} are {rec}, the best record through {n} games of any NBA team since 1946-47.",
        "No NBA team has ever been better through {n} games. {Team} are {rec}.",
        "At {rec}, {team} have the best {n}-game start in NBA history.",
        "{Team} are {rec} through {n} games, an NBA record since 1946-47.",
        "Nobody has started like this. {Team} are {rec} through {n} games, the best ever.",
        "Through {n} games, {team} are {rec}, better than any team in league history.",
        "{Team} are making history at {rec}, the best mark through {n} games of any team ever.",
        "The best start through {n} games in NBA history belongs to {team}, now {rec}.",
    ],
    "start-lg-ever-worst": [
        "{Team} are {rec}, the worst record through {n} games of any NBA team since 1946-47.",
        "No NBA team has ever been worse through {n} games. {Team} are {rec}.",
        "At {rec}, {team} have the worst {n}-game start in NBA history.",
        "{Team} are {rec} through {n} games, an NBA low since 1946-47.",
        "Nobody has started like this. {Team} are {rec} through {n} games, the worst ever.",
        "Through {n} games, {team} are {rec}, worse than any team in league history.",
        "{Team} are in uncharted territory at {rec}, the worst mark through {n} games of any team ever.",
        "The worst start through {n} games in NBA history belongs to {team}, now {rec}.",
    ],
    # ---- team streaks ----------------------------------------------------------------------------
    "streak-win-ever": [
        "{Team} have won {k} in a row, the longest streak in their {S} seasons.",
        "{Team} are on a {k}-game winning streak, a franchise record in {S} seasons.",
        "That's {k} straight wins for {team}, the longest run in franchise history ({S} seasons).",
        "{Team} keep winning. It's {k} in a row now, longer than any streak in their {S} seasons.",
        "Never before in {S} seasons have {team} won {k} straight. They have now.",
        "{Team} haven't lost in {k} games, their longest winning streak ever ({S} seasons).",
        "A franchise record for {team}, who have won {k} in a row, the best in {S} seasons.",
        "Make it {k} straight for {team}, the longest winning streak in their {S} seasons.",
    ],
    "streak-win-since": [
        "{Team} have won {k} in a row, their longest streak since {then}.",
        "{Team} are on a {k}-game winning streak, the franchise's longest since {then}.",
        "That's {k} straight wins for {team}, their best run since {then}.",
        "{Team} keep winning. It's {k} in a row now, their longest streak since {then}.",
        "The last time {team} won this many in a row was {then}. They're at {k} straight.",
        "{Team} haven't lost in {k} games, their longest winning streak since {then}.",
        "{Team} have stacked up {k} straight wins, the most in a row since {then}.",
        "Make it {k} straight for {team}, their longest winning streak since {then}.",
    ],
    "streak-lose-ever": [
        "{Team} have lost {k} in a row, the longest skid in their {S} seasons.",
        "{Team} are on a {k}-game losing streak, a franchise record in {S} seasons.",
        "That's {k} straight losses for {team}, the longest run in franchise history ({S} seasons).",
        "{Team} keep losing. It's {k} in a row now, longer than any skid in their {S} seasons.",
        "Never before in {S} seasons have {team} lost {k} straight.",
        "{Team} haven't won in {k} games, their longest losing streak ever ({S} seasons).",
        "A franchise low for {team}, who have dropped {k} in a row, the worst in {S} seasons.",
        "Make it {k} straight losses for {team}, the longest losing streak in their {S} seasons.",
    ],
    "streak-lose-since": [
        "{Team} have lost {k} in a row, their longest skid since {then}.",
        "{Team} are on a {k}-game losing streak, the franchise's longest since {then}.",
        "That's {k} straight losses for {team}, their worst run since {then}.",
        "{Team} keep losing. It's {k} in a row now, their longest skid since {then}.",
        "The last time {team} lost this many in a row was {then}. They're at {k} straight.",
        "{Team} haven't won in {k} games, their longest losing streak since {then}.",
        "{Team} have dropped {k} straight, the most in a row since {then}.",
        "Make it {k} straight losses for {team}, their longest losing streak since {then}.",
    ],
    # ---- with / without this season (wo = record without him, linked) -----------------------------------
    "ww-with": [
        "{Tm} are {wo} without {P} and {w} with him ({g} played, {m} missed).",
        "{Tm} are {w} when {P} plays and {wo} when he doesn't ({g} played, {m} missed).",
        "The split for {tm} with {P} this season is {w}, against {wo} without him ({g} played, {m} missed).",
        "With {P}, {tm} are {w}. Without him, {wo} ({g} played, {m} missed).",
        "{Tm} have gone {w} in the {g} games {P} has played and {wo} in the {m} he's missed.",
        "Big gap for {tm}, who are {w} with {P} and {wo} without him ({g} played, {m} missed).",
        "When {P} sits, {tm} are {wo}. When he plays, {w} ({g} played, {m} missed).",
        "{Tm} look like a different team with {P}, {w} with him and {wo} without ({g} played, {m} missed).",
    ],
    "ww-without": [
        "{Tm} are {wo} without {P} and {w} with him ({g} played, {m} missed).",
        "{Tm} are {w} when {P} plays and {wo} when he doesn't ({g} played, {m} missed).",
        "An odd split for {tm}, who are {wo} without {P} and {w} with him ({g} played, {m} missed).",
        "Without {P}, {tm} are {wo}. With him, {w} ({g} played, {m} missed).",
        "{Tm} have gone {wo} in the {m} games {P} has missed and {w} in the {g} he's played.",
        "Strange but true, {tm} are {wo} without {P} and {w} with him ({g} played, {m} missed).",
        "When {P} sits, {tm} are {wo}. When he plays, {w} ({g} played, {m} missed).",
        "{Tm} have the better record without {P} this season, {wo} to {w} ({m} missed, {g} played).",
    ],
    # ---- tonight's opponent (rec links to his row against them) ---------------------------------------------
    "tonight-good": [
        "{P} faces {opp} tonight. His teams are {rec} against them, {a} {pct} win rate.",
        "{P}'s teams are {rec} against {opp}, who they play tonight.",
        "{P} has owned {opp}, going {rec} in his career. They meet again tonight.",
        "Good sign for {P} tonight. His teams are {rec} against {opp}.",
        "{P} takes on {opp} tonight, a matchup his teams have won {won} times.",
        "Tonight {P} sees {opp} again. His teams have won {pct} of those games ({rec}).",
        "History favors {P} tonight against {opp}, with his teams at {rec} in the regular season.",
        "{Opp} have been a good matchup for {P}. His teams are {rec} against them, and they play tonight.",
    ],
    "tonight-bad": [
        "{P} faces {opp} tonight. His teams are {rec} against them, {a} {pct} win rate.",
        "Tough matchup for {P} tonight. His teams have gone {rec} against {opp}.",
        "{P}'s teams are just {rec} against {opp}, who they play tonight.",
        "{Opp} have had {P}'s number, {rec} against his teams. They meet again tonight.",
        "{P} gets {opp} tonight. His teams have won only {pct} of those games ({rec}).",
        "History isn't on {P}'s side tonight against {opp}, with his teams at {rec} in the regular season.",
        "{P} faces {opp} tonight. He's been on the winning side {tries}.",
        "{P}'s teams have struggled against {opp}, going {rec}. They play tonight.",
    ],
    # ---- from the archive / on this date ------------------------------------------------------------
    "archive-title": [
        "On this date in {season}, the {team} were {rec}. They finished {final} and won the title.",
        "The {season} {team} were {rec} on this date. They went on to finish {final} and win the championship.",
        "This date in {season} found the {team} at {rec}. They finished {final} and won the title.",
        "Remember the {season} {team}? On this date they were {rec}, on the way to a {final} finish and a title.",
        "On this date in {season}, the eventual champion {team} stood at {rec}. They finished {final}.",
        "The {team} were {rec} on this date in {season} and finished {final} with a championship.",
        "Looking back to {season}, the {team} were {rec} on this date. They ended at {final} and won the title.",
        "A title team on this date in {season}, the {team} were {rec} and finished {final}.",
    ],
    "archive-pace": [
        "On this date in {season}, the {team} were {rec}. They finished {final}, {ap} {pace}-win pace over 82 games.",
        "The {season} {team} were {rec} on this date. They finished {final}, {ap} {pace}-win pace over 82 games.",
        "This date in {season} found the {team} at {rec}. They finished {final}, good for {ap} {pace}-win pace.",
        "Remember the {season} {team}? On this date they were {rec}, on the way to {final}, {ap} {pace}-win pace.",
        "On this date in {season}, the {team} stood at {rec}. They ended at {final}, {ap} {pace}-win pace over 82 games.",
        "The {team} were {rec} on this date in {season} and finished {final}, {ap} {pace}-win pace.",
        "Looking back to {season}, the {team} were {rec} on this date. They finished {final}, {ap} {pace}-win pace over 82 games.",
        "{AP} {pace}-win pace team, the {season} {team} were {rec} on this date and finished {final}.",
    ],
    # ---- fun facts: perfect / winless in games he played or missed --------------------------------------
    "split-perfect-with": [
        "{Tm} are {rec} in the games {P} has played this season.",
        "{Tm} haven't lost with {P} in the lineup this season, {rec} in his {n} games.",
        "Perfect so far with {P}. {Tm} are {rec} when he plays.",
        "{P} has played {n} games for {tm} this season, and they've won all of them ({rec}).",
        "When {P} plays, {tm} win. They're {rec} with him this season.",
        "{Tm} are unbeaten with {P} on the floor this season ({rec}).",
        "Still no losses for {tm} with {P} playing, {rec} this season.",
        "It's {rec} for {tm} in the games {P} has played this season, still perfect.",
    ],
    "split-winless-with": [
        "{Tm} are {rec} in the games {P} has played this season.",
        "{Tm} haven't won with {P} in the lineup this season, {rec} in his {n} games.",
        "No wins yet for {tm} with {P} playing. They're {rec} with him.",
        "{P} has played {n} games for {tm} this season, and they've lost all of them ({rec}).",
        "{Tm} are still looking for a win with {P} on the floor ({rec}).",
        "{Tm} are winless in {P}'s {n} games this season ({rec}).",
        "A tough run for {P}, with {tm} {rec} in the games he's played this season.",
        "It's {rec} for {tm} in the games {P} has played this season.",
    ],
    "split-perfect-without": [
        "{Tm} are {rec} in the games {P} has missed this season.",
        "{Tm} haven't lost without {P} this season, {rec} in the {n} games he's missed.",
        "Perfect so far without {P}. {Tm} are {rec} when he sits.",
        "{P} has missed {n} games for {tm} this season, and they've won all of them ({rec}).",
        "{Tm} are unbeaten in the games {P} has missed this season ({rec}).",
        "Still no losses for {tm} when {P} sits out, {rec} this season.",
        "When {P} sits, {tm} are {rec} this season.",
        "It's {rec} for {tm} in the games {P} has missed this season, still perfect.",
    ],
    "split-winless-without": [
        "{Tm} are {rec} in the games {P} has missed this season.",
        "{Tm} haven't won without {P} this season, {rec} in the {n} games he's missed.",
        "No wins yet for {tm} when {P} sits. They're {rec}.",
        "{P} has missed {n} games for {tm} this season, and they've lost all of them ({rec}).",
        "{Tm} are still looking for a win without {P} ({rec}).",
        "{Tm} are winless in the {n} games {P} has missed this season ({rec}).",
        "When {P} sits, {tm} are {rec} this season.",
        "It's {rec} for {tm} in the games {P} has missed this season.",
    ],
    # ---- fun facts: a player's run of seasons (n links to his season table) ---------------------------
    "career-winning": [
        "{P}'s teams have had a winning record in each of his last {n} ({span}), {tag}.",
        "{P} has been on a winning team {n} straight ({span}), {tag}.",
        "Winning is a habit for {P}, whose teams have finished above .500 in each of his last {n} ({span}). That's {tag}.",
        "{P} hasn't played for a losing team in his last {n} ({span}), {tag}.",
        "Every one of {P}'s last {n} has ended with a winning record ({span}), {tag}.",
        "{P}'s run of winning seasons is up to {n} ({span}), {tag}.",
        "Going back {n} ({span}), {P}'s teams have finished above .500 every time. That's {tag}.",
        "{P} keeps landing on winners, {n} in a row ({span}), {tag}.",
    ],
    "career-drought": [
        "{P} has not been on a playoff team in his last {n} ({span}), {tag}.",
        "{P}'s playoff drought is up to {n} ({span}), {tag}.",
        "It's been {n} since {P} played for a playoff team ({span}). That's {tag}.",
        "{P}'s teams have missed the playoffs in each of his last {n} ({span}), {tag}.",
        "No playoffs for {P} in his last {n} ({span}), {tag}.",
        "Going back {n} ({span}), {P} hasn't reached the playoffs. That's {tag}.",
        "{P} is still waiting for a playoff trip, now {n} without one ({span}), {tag}.",
        "Every one of {P}'s last {n} has ended without a playoff trip ({span}), {tag}.",
    ],
    # ---- fun facts: with and without a teammate (tag links to the pair's row) --------------------------
    "mates-drop": [
        "{P}'s teams are {t} ({tp}) with {Q} and {o} ({op}) without him, {gap} points lower. That's {tag}.",
        "{P} wins a lot more with {Q} around. His teams are {t} with him and {o} without, a {gap}-point drop, {tag}.",
        "With {Q}, {P}'s teams win {tp} of the time. Without him, {op}. That {gap}-point gap is {tag}.",
        "Take {Q} away and {P}'s teams drop from {tp} to {op}, {gap} points, {tag}.",
        "{P}'s teams are {gap} points worse without {Q} ({t} with, {o} without), {tag}.",
        "Few drops are as steep as this one. {P}'s teams are {t} with {Q} and {o} without him, {tag}.",
        "{P}'s record with {Q} is {t}. Without him it's {o}, a {gap}-point difference and {tag}.",
        "{P} has won {tp} of the games he's played alongside {Q} and {op} without him, {tag}.",
    ],
    "mates-together": [
        "{P} and {Q} have played {n} games together and gone {rec}, {tag}.",
        "{P} and {Q} keep winning together. They're {rec} in {n} games, {tag}.",
        "In {n} games side by side, {P} and {Q} are {rec}. That's {tag}.",
        "When {P} and {Q} both play, their teams are {rec} in {n} games, {tag}.",
        "{P} and {Q} make a winning pair, {rec} in {n} games together, {tag}.",
        "Few teammates win like {P} and {Q}, who are {rec} in {n} games together. That's {tag}.",
        "{P} and {Q} are {rec} in their {n} games as teammates, {tag}.",
        "Put {P} and {Q} together and their teams are {rec} over {n} games, {tag}.",
    ],
}

# the slots every template of a set must use (its links), checked by tests/test_phrasing.py
REQUIRED = {
    "wins-mark": ("P", "M"), "wl-mark-up": ("P", "M"), "wl-mark-down": ("P", "M"),
    "wins-pass": ("P", "names", "rank"), "wl-pass": ("P", "names", "rank"),
    "pct-top": ("P", "rank"), "pct-pass": ("P", "names", "rank"),
    "ww-with": ("P", "wo"), "ww-without": ("P", "wo"),
    "tonight-good": ("P", "rec"), "tonight-bad": ("P", "rec"),
    "archive-title": ("team",), "archive-pace": ("team",),
    "career-winning": ("P", "n"), "career-drought": ("P", "n"),
    "mates-drop": ("P", "Q", "tag"), "mates-together": ("P", "Q", "rec"),
}
for _k in SETS:
    if _k.startswith("start-"):
        REQUIRED[_k] = ("team", "then") if "-since-" in _k else ("team",)
    elif _k.startswith("streak-"):
        REQUIRED[_k] = ("team",)
    elif _k.startswith("split-"):
        REQUIRED[_k] = ("P",)

SLOT_RE = re.compile(r"\{(\w+)\}")
OPT_RE = re.compile(r"\[\[(.*?)\]\]")
# a slot and its capitalised twin are the same link ("{Team}" / "{team}")
TWINS = {"Team": "team", "Tm": "tm", "Opp": "opp", "AP": "ap",
         # the same record link, worded "30 of 37" / "only 2 times in 25 tries"
         "won": "rec", "tries": "rec"}


def slots_of(tpl):
    return {TWINS.get(s, s) for s in SLOT_RE.findall(tpl)}


def pick(kind, date, subject, used):
    """(index, template) for one item: a hash of (date, kind, subject), stepping past templates already
    used in this list or strip (used: a set of (kind, index), updated here)."""
    tpls = SETS[kind]
    h = int(hashlib.sha1(f"{date}|{kind}|{subject}".encode()).hexdigest(), 16)
    for step in range(len(tpls)):
        i = (h + step) % len(tpls)
        if (kind, i) not in used:
            used.add((kind, i))
            return i, tpls[i]
    i = h % len(tpls)                       # more items of one kind than templates: cannot happen (caps < 7)
    return i, tpls[i]


def _value(v):
    """str -> one text part; [text, href, bold] -> that part; [[...], ...] -> those parts."""
    if isinstance(v, str):
        return [[v]]
    if v and isinstance(v[0], list):
        return [list(x) for x in v]
    return [list(v)]


def render(tpl, slots):
    """Template + slot values -> parts ([text] or [text, href, bold]); optional [[...]] pieces with a
    missing slot are left out; adjacent text parts are merged."""
    def keep(m):
        inner = m.group(1)
        return inner if all(slots.get(s) is not None for s in SLOT_RE.findall(inner)) else ""
    tpl = OPT_RE.sub(keep, tpl)
    parts = []
    pos = 0
    for m in SLOT_RE.finditer(tpl):
        if m.start() > pos:
            parts.append([tpl[pos:m.start()]])
        v = slots[m.group(1)]
        parts.extend(_value(v))
        pos = m.end()
    if pos < len(tpl):
        parts.append([tpl[pos:]])
    for a, b in zip(parts, parts[1:]):
        # AP style: "Aaron Wiggins' teams", not "Wiggins's"
        if len(a) == 3 and a[0].endswith("s") and len(b) == 1 and b[0].startswith("'s"):
            b[0] = "'" + b[0][2:]
    out = []
    for p in parts:
        if len(p) == 1 and out and len(out[-1]) == 1:
            out[-1] = [out[-1][0] + p[0]]
        elif p[0] != "" or len(p) > 1:
            out.append(p)
    return out


def article(num_text):
    """'a' or 'an' before a number as read aloud: an 8.0%, an 11-game, an 18.2%, an 80-win."""
    t = num_text.lstrip("+")
    return "an" if t.startswith("8") or re.match(r"(11|18)(\D|$)", t) else "a"


def plain(v):
    """The text a slot value shows, whatever its shape."""
    if v is None:
        return ""
    return "".join(p[0] for p in _value(v))


def signature(slots):
    """A fact's data as one string (slot name = shown text), independent of the template: the no-repeat key."""
    return "/".join(f"{k}={plain(v)}" for k, v in sorted(slots.items()))


def text(parts):
    return "".join(p[0] for p in parts)
