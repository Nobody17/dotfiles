---
name: codex-review-plan
description: >-
  Plan-Gegenprüfung durch Codex in Herdr vor der Umsetzung. Verwenden, wenn
  der Nutzer einen zweiten Agenten zum Review der Planung oder zum gemeinsamen
  Review von Spec und Tickets verlangt. Spec und Tickets werden auf Wunsch
  einbezogen. Für fertigen Code: codex-review-code.
---

# Plan-Review mit einem zweiten Agenten

Lies vor dem ersten Pane-Steuerbefehl das installierte Skill `herdr`. Prüfe dort
die Voraussetzung `HERDR_ENV=1` und befolge die Regeln für CLI, Agentenstart,
blockierte Zustände und das Lesen vollständiger Antworten.

Das Ergebnis ist eine **geprüfte, überarbeitete Planung**, einschließlich der
zum Review gehörenden Dokumente. Die Umsetzung beginnt erst nach Freigabe.
Im Plan-Modus gehört das Review vor `ExitPlanMode`.

## Umfang festlegen

Standard ist die Planung aus dem laufenden Gespräch oder einer vorhandenen
Plandatei. **Spec und Tickets sind optional:** Beziehe sie ein, wenn der Nutzer
ihre Prüfung verlangt. Ihre bloße Existenz erweitert den Auftrag nicht.

Für ein gemeinsames Review bleib nach `/to-tickets` im selben Gespräch, vor
`/clear` und vor der Umsetzung. Prüfe Spec und vollständigen Ticketsatz in
einer gemeinsamen Schleife. Eine separate Plandatei ist dafür nicht nötig;
arbeite mit den vorhandenen Unterlagen, ohne fehlende Dokumenttypen anzulegen.

## Reviewer wählen

Ermittle den absoluten Pfad des Ziel-Worktrees mit `git rev-parse --show-toplevel`
im Projektverzeichnis. Prüfe vorhandene bereite Codex-Agenten mit `herdr agent list`.
Lass einen Kandidaten sein Arbeitsverzeichnis und seine Ausgabe von
`git rev-parse --show-toplevel` nennen. Verwende ihn nur, wenn der Worktree
dem Ziel entspricht; sonst starte nach `herdr` einen Reviewer im Ziel-Worktree.
Ist das Skill `herdr-pane-mute` installiert, schalte den neuen Pane vor dem
Start des Reviewers so stumm, wie es das Skill beschreibt.
Gib ihm einen eindeutigen Namen und behalte ihn über alle Runden. Die Beispiele
verwenden `planner-review` (`herdr agent rename <pane-id> planner-review`).

## Review-Kontext übergeben

Lies die zum Auftrag gehörenden Dateien vollständig. Der Reviewer sieht den
Gesprächsverlauf nicht: Übergib ihm die Planung aus dem Gespräch oder die
Quellenverweise und ergänze Entscheidungen, Gründe, Grenzen und offene Fragen
aus der Grilling-Historie, soweit sie in den Quellen fehlen.

Dieser Review-Kontext steht im Prompt; bei größerem Umfang darf er in eine
temporäre Scratchpad-Datei. Er ist eine Übergabe, kein zusätzliches Plandokument.
Nenne den absoluten Ziel-Worktree sowie alle Quelldateien mit absoluten Pfaden
beziehungsweise Tracker-Links mit ihrem gelesenen Inhalt.

Der Reviewer braucht:

- das Ziel, den Ziel-Worktree und woran Erfolg gemessen wird
- die Annahmen über den Bestand, jede als solche gekennzeichnet
- die Schritte in ihrer Reihenfolge, mit Abhängigkeiten
- was ausdrücklich **nicht** dazugehört
- die Stellen, an denen du selbst unsicher bist

### Wenn Spec oder Tickets einbezogen sind

Prüfe zusätzlich in derselben Runde:

- Spec: vollständige, widerspruchsfreie Anforderungen, klare Grenzen und
  überprüfbare Ergebnisse.
- Tickets: eindeutige Akzeptanzkriterien, einzeln überprüfbare Ergebnisse,
  passende Größe und korrekte Blocker ohne Zyklen.
- Zusammenhang, wenn Spec und Tickets vorliegen: Jede Anforderung der Spec ist
  durch Tickets abgedeckt; Tickets und Gesprächsentscheidungen stimmen mit der
  Spec überein. Lies dafür auch die übergeordnete Spec und die verknüpften
  Tickets, soweit vorhanden.

## Prompt

Sende den Review-Kontext als Freitext-Auftrag und ergänze die zum Umfang
gehörenden Prüffragen aus dem vorigen Abschnitt:

```bash
herdr agent prompt planner-review "Review-Kontext: <Planung, Quellen und
Gesprächsentscheidungen>. Prüfe diesen Umfang gemeinsam gegen den Code in
<absoluter-worktree-pfad>. Fragen: Stimmen die Annahmen über den
Bestand? Fehlen Schritte, ohne die das Vorhaben nicht läuft? Ist die
Reihenfolge haltbar oder hängt Schritt N von etwas ab, das erst später kommt?
Was lässt sich nicht testen? Wo ist der Plan aufwendiger als nötig, gibt es
einen einfacheren Weg zum gleichen Ziel? Nenne nur konkrete Einwände mit Datei
und Zeile oder mit dem Schritt, den sie betreffen. Ändere keine Dateien und
setze nichts um. Schließe mit den geprüften Quellenständen und den offenen Einwänden
ab; bestätige ausdrücklich, wenn keine offen sind." --wait --timeout 60000
```

Bei einem Timeout prüfst du den Agentenzustand und wartest bei laufendem Review
weiter. Lies die vollständige Antwort nach den `herdr`-Regeln.

## Einwände einordnen

Prüfe jeden Einwand am Code, den Quellen und den Entscheidungen im Gespräch
und ordne ihn ein:

**Sachfehler oder Lücke.** Eine Aussage über den Bestand ist falsch, eine
Anforderung fehlt oder die Unterlagen widersprechen einander. Das korrigierst
du selbst in den betroffenen Quellen.

**Falscher Einwand.** Widersprich im nächsten Prompt mit Begründung.

**Echte Weggabelung.** Zwei Umsetzungen sind beide vertretbar und führen zu
merklich verschiedener Arbeit, verschiedenem Aufwand oder verschiedenen
Folgekosten. Gibt es einen naheliegenden Standard, entscheide selbst und
kennzeichne die Entscheidung in der Planung als Annahme. Sonst frage mit
`AskUserQuestion`:

- eine Frage je Weggabelung
- höchstens vier Fragen, lieber zwei
- die Optionen sind die wirklichen Alternativen, mit ihren Folgen in der
  Beschreibung, nicht bloß Etiketten
- die von dir empfohlene Option zuerst, mit "(Empfohlen)"
- keine Frage nach Zustimmung zum Plan als Ganzem, das macht `ExitPlanMode`
- alles, was nicht von der Antwort abhängt, vorher fertig denken, damit eine
  Antwort auch wirklich weiterhilft

Halte Nutzerentscheidungen in den betroffenen Quelldokumenten fest. Existiert
nur die Planung im Gespräch, aktualisiere sie dort. Der temporäre Review-Kontext
ersetzt keine Quelle.

## Weitere Runden

Aktualisiere die betroffenen Quellen und den Review-Kontext, dann frage denselben
Pane erneut zum gemeinsamen Umfang. Der Prompt nennt, was sich geändert hat und
warum, welche Einwände du zurückgewiesen hast und welche Entscheidungen vom
Nutzer kommen. Übergib erneut Ziel-Worktree und Quellenverweise. Ergänze: „Prüfe jede
Korrektur und Zurückweisung. Melde fortbestehende Einwände erneut mit Beleg;
bestätigte Lösungen sind erledigt. Nutzerentscheidungen sind Vorgaben; melde
konkrete Widersprüche oder bislang unbeachtete Folgen dieser Vorgaben.“

## Abschluss prüfen

Erfolgreich abgeschlossen ist das Review erst mit einer vollständig gelesenen
Abschlussantwort zum aktuellen Review-Kontext, allen einbezogenen Quellen und
zum Ziel-Worktree, die ausdrücklich keine offenen Einwände bestätigt. Nach einer
Änderung dieser Inhalte ist eine neue Runde nötig.
Leere, abgeschnittene, blockierte oder unterbrochene Antworten sind unvollständig;
kläre den Zustand nach `herdr`, bevor du das Ergebnis wertest.

Nach drei Runden mit offenem Ergebnis stoppen und die offenen Punkte dem Nutzer
vorlegen, einschließlich der Einwände, die du für falsch hältst.

## Bericht

Pro Runde: welche Einwände kamen, welche echt waren, was du korrigiert hast,
was der Nutzer entschieden hat, was offen bleibt. Unterscheide erfolgreichen
Abschluss von einem Stopp mit offenen Einwänden oder unvollständigem Review.
Nenne die geprüften und geänderten Quellen und stelle die überarbeitete Planung
zur Freigabe.
