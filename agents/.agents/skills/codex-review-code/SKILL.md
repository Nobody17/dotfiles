---
name: codex-review-code
description: >-
  Code-Gegenprüfung durch Codex in Herdr mit Korrekturschleife. Verwenden, wenn
  der Nutzer einen zweiten Agenten zum Review von Code verlangt. Für Pläne:
  codex-review-plan. Ein gewöhnliches Review oder /code-review genügt nicht
  als Auslöser.
---

# Review-Schleife mit einem zweiten Agenten

Lies vor dem ersten Pane-Steuerbefehl das installierte Skill `herdr`. Prüfe dort
die Voraussetzung `HERDR_ENV=1` und befolge die Regeln für CLI, Agentenstart,
blockierte Zustände und das Lesen vollständiger Antworten.

## Werkzeug für Gegenproben wählen

Prüfe vor dem Reviewer-Start die Projektanweisungen, Build-/Testkonfiguration
und bereits getroffene Nutzerentscheidungen auf Mutation Testing oder einen
vereinbarten Gegenproben-Befehl. Verwende die vorhandene Einrichtung und beachte
Sprache, Compiler, Testframework und betroffenen Teil des Projekts.

Fehlt eine nutzbare Einrichtung und ist die Werkzeugwahl noch offen, frage den
Nutzer gezielt, welches Mutation-Testing-Werkzeug dieses Projekt verwenden soll.
Nenne passende Kandidaten mit einer Empfehlung und dem jeweiligen Aufwand;
prüfe dafür aktuelle Kompatibilität, Lizenz, Pflege und Projekthistorie.
Bevorzuge passende Open-Source-Werkzeuge. Frage auch nach einem möglicherweise
vorhandenen, noch nicht dokumentierten Werkzeug oder Befehl. Falls kein geeigneter
Kandidat gefunden wird, benenne die Lücke und frage, ob für diesen Umfang
gezielte manuelle Gegenproben verwendet werden sollen.

Warte mit werkzeugabhängigen Schritten auf die Antwort. Installiere in dieser
Situation weder selbst ein Ersatzwerkzeug noch baue einen eigenen Runner.
Unabhängige Prüfung und Vorbereitung können weitergehen. Ein delegierter Agent
meldet die Frage an den Orchestrator; dieser bündelt sie für den Nutzer.
Halte die getroffene Wahl und, sobald eingerichtet, Version, Konfiguration und
Befehl im projektspezifischen Testhinweis fest. Frage bei späteren Reviews nicht
erneut, solange die Entscheidung noch passt; erläutere eine Unverträglichkeit,
bevor du eine neue Wahl anforderst.

## Reviewer wählen

Ermittle den absoluten Pfad des Ziel-Worktrees mit `git rev-parse --show-toplevel`
im Projektverzeichnis. Halte den Review-Umfang fest: uncommittete Änderungen,
Commit oder Vergleichsbasis.

Prüfe vorhandene bereite Codex-Agenten mit `herdr agent list`. Lass einen
Kandidaten vor dem Review sein Arbeitsverzeichnis und seine Ausgabe von
`git rev-parse --show-toplevel` nennen. Verwende ihn nur, wenn der Worktree
dem Ziel entspricht; sonst starte nach `herdr` einen Reviewer im Ziel-Worktree.
Ist das Skill `herdr-pane-mute` installiert, schalte den neuen Pane vor dem
Start des Reviewers so stumm, wie es das Skill beschreibt.
Gib ihm einen eindeutigen Namen und behalte ihn über alle Runden; `reviewer`
ist in den Beispielen dieser Name:

```bash
herdr agent rename <pane-id> reviewer
```

## Schwere Befehle

Gibt dein Auftrag eine Form für schwere Befehle vor (Tests, Builds; zum Beispiel
`heavy-job.py` einer Orchestrierung), prüft der Reviewer nur lesend. Jeder
Prompt an ihn enthält dann: "Führe keine Tests und Builds aus. Brauchst du einen
Lauf, nenne Befehl und Zweck; ich führe ihn aus und gebe dir das Ergebnis."
Wähle in Runde 1 dafür den Preset „Custom review instructions“ und gib dort den
Review-Umfang und diesen Satz ein; nur dieser Preset nimmt eine eigene Anweisung
an. Führe angeforderte Läufe in der Form deines Auftrags aus. Zeigt eine Antwort einen eigenen Lauf des
Reviewers, nenne ihn im Bericht.

## Vor der ersten Runde

Belege jede neue Zusage mit einer Gegenprobe über das gewählte Werkzeug oder
das vereinbarte manuelle Verfahren. Die Gegenprobe verändert das Verhalten des
Produktivcodes; der zugehörige Test muss den eingebauten Fehler erkennen.
Ordne den Nachweis der Zusage und dem geprüften Code-Stand zu. Ein Gesamtwert
für Mutationsabdeckung ersetzt diese Zuordnung nicht. Compilerfehler,
Werkzeugfehler, Zeitüberschreitungen und Unterbrechungen sind kein solcher Nachweis.
Der unveränderte Stand muss bestehen. Stelle bei Quelltextmutationen den
ursprünglichen Stand wieder her und prüfe ihn erneut; bewahre die Ergebnisse
abgeschlossener Gegenproben für eine Fortsetzung auf.

**Nicht committen.** Wähle in Runde 1 den Preset für den festgelegten Umfang.

## Runde 1: Codex' eigenes /review

```bash
herdr agent prompt reviewer "/review"
```

Lies nach dem separaten Slash-Prompt das Menü. Bei `agent_prompt_stalled`
prüfst du ebenfalls zuerst den sichtbaren Zustand nach den `herdr`-Regeln:

```bash
herdr agent read reviewer --source visible --lines 15
```

Wähle den passenden Preset anhand seiner sichtbaren Beschriftung. Für lokale
Änderungen ist das „Review uncommitted changes“; bei einer Form für schwere
Befehle gilt [Schwere Befehle](#schwere-befehle). Navigiere zur Auswahl, lies
die Markierung erneut und bestätige erst, wenn sie beim gewünschten Preset steht:

```bash
herdr agent send-keys reviewer enter
herdr agent wait reviewer --timeout 60000
herdr agent read reviewer --source recent-unwrapped --lines 250
```

Bei einem Timeout prüfst du den Agentenzustand und wartest bei laufendem Review
weiter. Meldet der Reviewer einen leeren Worktree, prüfe Ziel und Umfang erneut.
Ein leerer Diff belegt kein abgeschlossenes Review des gewünschten Codes.

## Runde 2 und weiter: Freitext

Für die Prüfung der Korrekturen sende einen Freitext-Prompt. Er enthält:

- den absoluten Ziel-Worktree und den Review-Umfang
- die geänderten Dateien, untracked ausdrücklich benannt
- das Ziel der Änderung in einem Satz
- was du aus der Vorrunde geändert hast und mit welcher Begründung
- die konkreten Zweifel als Fragen, nicht als Aufgabe
- "Nenne nur konkrete Findings mit Datei und Zeile, keine Stilfragen"
- "Ändere keine Dateien"
- bei einer Form für schwere Befehle den Satz aus [Schwere Befehle](#schwere-befehle)
- "Prüfe jede behauptete Korrektur und jede Zurückweisung. Melde einen Punkt
  erneut mit Beleg, wenn der Fehler fortbesteht; bestätigte Lösungen sind erledigt."
- "Schließe mit dem geprüften Stand und den offenen Findings ab; bestätige
  ausdrücklich, wenn keine offen sind."

## Findings behandeln

Prüfe jedes Finding anhand seines Fehlerfalls. Korrigiere belegte Fehler;
widersprich falschen Findings im nächsten Prompt mit Begründung.

Nach jeder Korrektur die eigenen Tests laufen lassen und für jede neu
hinzugekommene Zusage die Gegenprobe wiederholen.

## Abschluss prüfen

Erfolgreich abgeschlossen ist das Review erst mit einer vollständig gelesenen
Abschlussantwort zum aktuellen Ziel und Code-Stand, die ausdrücklich keine
offenen Findings bestätigt. Nach einer weiteren Änderung ist eine neue Runde nötig.
Leere, abgeschnittene, blockierte oder unterbrochene Antworten sind unvollständig;
kläre den Zustand nach `herdr`, bevor du das Ergebnis wertest.

Nach vier Runden oder wenn derselbe Streitpunkt trotz Begründung erneut offen
bleibt: mit offenem Ergebnis stoppen und den Nutzer entscheiden lassen. Ein
erneut belegter Fehler nach einem Korrekturversuch geht zurück in die Korrektur,
solange das Rundenlimit nicht erreicht ist.

## Bericht

Pro Runde: Findings, Belege, Korrekturen und Zurückweisungen. Nenne den geprüften
Stand und unterscheide erfolgreichen Abschluss von einem Stopp mit offenen
Findings oder unvollständigem Review.
