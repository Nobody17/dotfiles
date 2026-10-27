---
name: codex-review-code
description: >-
  Lässt einen zweiten Agenten (Codex) in einem Herdr-Pane die eigene Arbeit
  gegenlesen und arbeitet dessen Findings ab, bis keine mehr kommen. Runde 1
  über Codex' eigenes /review, danach Freitext. Trigger: "lass Codex
  gegenlesen", "codex review code", "gegenlesen bis nichts mehr kommt", "zweite
  Meinung zu meinem Patch", "Codex soll das reviewen". Nur wenn der Nutzer die
  Gegenprüfung durch einen anderen Agenten will, nicht für /code-review. Für
  einen Plan statt fertigem Code: codex-review-plan.
---

# Review-Schleife mit einem zweiten Agenten

Voraussetzung: `HERDR_ENV=1`. Das Skill `herdr` kennt die CLI, hier steht nur
das Verfahren. Geht es um einen Plan und nicht um fertigen Code, ist
`codex-review-plan` das Gegenstück: gleiche Schleife, aber Weggabelungen gehen
dort als Frage an den Nutzer.

## Reviewer wählen

Nimm einen vorhandenen idle-Agenten der gewünschten Art statt einen neuen zu
starten: `herdr agent list`. Gib ihm einmal einen Namen und behalte ihn über
alle Runden:

```bash
herdr agent rename <pane-id> reviewer
```

Derselbe Pane behält seinen Kontext. Spätere Runden werden dadurch deutlich
kürzer, weil der Reviewer den Code schon kennt.

## Vor der ersten Runde

Belege jede neue Zusage mit einer Gegenprobe, bevor du sie zum Review gibst:
brich die Eigenschaft im Produktivcode absichtlich, lass den Test laufen,
stelle den Code wieder her. Ein Test, der grün bleibt, wenn man das
Versprechen bricht, ist kein Test.

**Nicht committen.** Runde 1 liest die uncommitteten Änderungen. Nach einem
Commit findet der Reviewer nichts mehr vor.

## Runde 1: Codex' eigenes /review

Codex bringt einen eigenen Review-Prompt mit. Der ist besser als ein selbst
gebauter Freitext, also fängst du damit an.

```bash
herdr agent prompt reviewer "/review"
```

Das antwortet mit `agent_prompt_stalled`. **Das ist kein Fehler und kein Grund,
den Befehl zu wiederholen.** Der Text ist abgeschickt, aber ein geöffnetes
Menü ist keine Lebenszyklus-Änderung, also greift Herdrs 5-Sekunden-Regel.

Menü prüfen, nicht raten:

```bash
herdr agent read reviewer --source visible --lines 15
```

Erwartet wird "Select a review preset" mit vier Einträgen, Position 1
vorgewählt (`›`):

```
› 1. Review against a base branch  (PR Style)
  2. Review uncommitted changes
  3. Review a commit
  4. Custom review instructions
```

Preset 2 ist der Normalfall. Einen Schritt nach unten, **Auswahl lesen**, erst
dann bestätigen:

```bash
herdr agent send-keys reviewer down
herdr agent read reviewer --source visible --lines 15   # steht › vor 2.?
herdr agent send-keys reviewer enter
herdr agent wait reviewer --until idle --until done --timeout 900000
herdr agent read reviewer --source recent-unwrapped --lines 250
```

Niemals `enter` blind schicken. Ändert Codex die Reihenfolge der Presets, oder
war das Menü nie offen, landet der Tastendruck sonst irgendwo.

Meldet der Reviewer "The working tree contains no staged, unstaged, or
untracked changes to review", ist bereits committed. Dann Preset 3 für einen
Commit nehmen oder in Runde 2 mit Freitext und `git show <sha>` arbeiten.

## Runde 2 und weiter: Freitext

`/review` kann nur "sieh dir den Diff an". Für "prüfe, ob mein Fix stimmt"
brauchst du einen eigenen Prompt. Er enthält:

- die geänderten Dateien, untracked ausdrücklich benannt
- das Ziel der Änderung in einem Satz
- was du aus der Vorrunde geändert hast und mit welcher Begründung
- die konkreten Zweifel als Fragen, nicht als Aufgabe
- "Nenne nur konkrete Findings mit Datei und Zeile, keine Stilfragen"
- "Ändere keine Dateien"
- "Keine Wiederholung bereits behobener Punkte"

Das letzte Paar ist wichtig: ein Reviewer, der selbst schreibt, verwischt die
Verantwortung, und ohne die Sperre gegen Wiederholung wächst jede Runde.

## Findings behandeln

Jedes Finding einzeln prüfen, nicht sammeln und abnicken. Ein Finding ist erst
echt, wenn du den Fehlerfall selbst nachvollzogen hast.

**Widersprich falschen Findings im nächsten Prompt mit Begründung, statt den
Code anzupassen, damit Ruhe ist.** Die Abbruchbedingung ist "der Reviewer
schweigt", und die belohnt Nachgeben. Dagegen hilft nur, jedes Finding zu
belegen, bevor du es befolgst.

Nach jeder Korrektur die eigenen Tests laufen lassen und für jede neu
hinzugekommene Zusage die Gegenprobe wiederholen.

## Lesen

`--source recent-unwrapped` für Transkripte. Fehlen eingeklappte Details
("… +402 lines"), liegen sie im Alternate Screen und sind über `--lines` nicht
erreichbar. Dann den Reviewer bitten, seine Antwort als Markdown in eine
Temp-Datei zu schreiben und nur den Pfad zu nennen, und die Datei lesen.

## Abbruch

Fertig, wenn eine Runde keine Findings mehr liefert. Nach vier Runden, oder
wenn dieselbe Frage ein zweites Mal aufkommt: abbrechen, den offenen Punkt
benennen, den Nutzer entscheiden lassen. Eine Schleife ohne Obergrenze kostet
unbemerkt viel.

## Bericht

Pro Runde die Findings nennen und ob sie echt waren. Ob alle Findings echt
waren, ist die Aussage, die den Aufwand rechtfertigt oder eben nicht.
