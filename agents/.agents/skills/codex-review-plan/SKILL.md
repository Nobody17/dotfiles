---
name: codex-review-plan
description: >-
  Lässt einen zweiten Agenten (Codex) in einem Herdr-Pane einen Plan
  gegenlesen, bevor er umgesetzt wird, und arbeitet dessen Einwände ab.
  Sachfehler und Lücken werden selbst korrigiert, echte Weggabelungen gehen
  als Frage an den Nutzer. Trigger: "lass Codex den Plan reviewen", "codex review
  plan", "zweite Meinung zum Plan", "Plan gegenlesen lassen", "prüf den Plan
  mit Codex". Nur für Pläne und Vorhaben, nicht für fertigen Code (dafür
  codex-review-code).
---

# Plan-Review mit einem zweiten Agenten

Voraussetzung: `HERDR_ENV=1`. Das Skill `herdr` kennt die CLI, `codex-review-code`
das gleiche Verfahren für fertigen Code. Hier steht, was bei einem Plan anders
ist.

Das Ergebnis dieses Skills ist ein **überarbeiteter Plan**, nicht Code. Nicht
mit der Umsetzung anfangen, auch nicht mit dem "offensichtlichen" ersten
Schritt. Läuft die Sitzung im Plan-Modus, gehört das Review **vor**
`ExitPlanMode`, damit der Nutzer den geprüften Plan freigibt und nicht den
ungeprüften.

## Reviewer wählen

Wie in `codex-review-code`: vorhandenen idle-Agenten nehmen, einmal benennen
(`herdr agent rename <pane-id> planner-review`), über alle Runden behalten.

## Den Plan übergeben

Der Reviewer kann den Plan nicht sehen, solange er nur im Gespräch steht.
Schreib ihn als Markdown in eine Datei und nenne den **absoluten** Pfad, denn
der Pane hat sein eigenes Arbeitsverzeichnis. Ohne besonderen Wunsch in das
Scratchpad-Verzeichnis der Sitzung, nicht in das Repo.

Der Plan im Review braucht mehr als die Schritte:

- das Ziel und woran Erfolg gemessen wird
- die Annahmen über den Bestand, jede als solche gekennzeichnet
- die Schritte in ihrer Reihenfolge, mit Abhängigkeiten
- was ausdrücklich **nicht** dazugehört
- die Stellen, an denen du selbst unsicher bist

Der letzte Punkt ist der wertvollste. Ein Plan, der seine Unsicherheiten
verschweigt, bekommt ein Review über die falschen Stellen.

## Prompt

Freitext, kein `/review`: dessen Presets lesen einen Diff, hier gibt es keinen.

```bash
herdr agent prompt planner-review "Lies den Plan in <absoluter-pfad>. Prüfe
ihn gegen den Code in diesem Repo. Fragen: Stimmen die Annahmen über den
Bestand? Fehlen Schritte, ohne die das Vorhaben nicht läuft? Ist die
Reihenfolge haltbar oder hängt Schritt N von etwas ab, das erst später kommt?
Was lässt sich nicht testen? Wo ist der Plan aufwendiger als nötig, gibt es
einen einfacheren Weg zum gleichen Ziel? Nenne nur konkrete Einwände mit Datei
und Zeile oder mit dem Schritt, den sie betreffen. Keine Stilfragen, keine
Zustimmung. Ändere keine Dateien und setze nichts um." --wait --timeout 900000
```

"Keine Zustimmung" gehört hinein, weil ein Plan-Review sonst zur Hälfte aus
Lob besteht, das nichts trägt.

## Einwände einordnen

Jeden Einwand einzeln prüfen, am Code, nicht am Gefühl. Dann in genau eine der
drei Klassen einordnen, denn davon hängt ab, wer entscheidet:

**Sachfehler oder Lücke.** Der Plan behauptet etwas Falsches über den Bestand,
oder ein Schritt fehlt. Das korrigierst du selbst, ohne zu fragen. Es gibt
nichts zu entscheiden, es ist einfach falsch.

**Echte Weggabelung.** Zwei Umsetzungen sind beide vertretbar und führen zu
merklich verschiedener Arbeit, verschiedenem Aufwand oder verschiedenen
Folgekosten. **Hier fragst du den Nutzer** mit `AskUserQuestion`, statt still
zu wählen. Typisch: Datenmodell so oder anders schneiden, bestehenden Dienst
erweitern oder neben ihn treten, jetzt migrieren oder später, Umfang größer
oder kleiner.

**Falscher Einwand.** Der Reviewer irrt. Widersprich im nächsten Prompt mit
Begründung, statt den Plan anzupassen, damit Ruhe ist.

## Wann wirklich gefragt wird

Nicht jede Wahl ist eine Weggabelung. Frag nur, wenn die Antwort die Arbeit
ändert. Gibt es einen naheliegenden Standard, entscheide selbst, nenne die
Entscheidung im Plan als Annahme und mach weiter.

Für die Fragen selbst:

- eine Frage je Gabelung, nicht mehrere Themen in eine gepackt
- höchstens vier Fragen, lieber zwei
- die Optionen sind die wirklichen Alternativen, mit ihren Folgen in der
  Beschreibung, nicht bloß Etiketten
- die von dir empfohlene Option zuerst, mit "(Empfohlen)"
- keine Frage nach Zustimmung zum Plan als Ganzem, das macht `ExitPlanMode`
- alles, was nicht von der Antwort abhängt, vorher fertig denken, damit eine
  Antwort auch wirklich weiterhilft

Antwortet der Nutzer, schreib die Entscheidung in den Plan, nicht nur in die
Antwort. Sonst geht sie in der nächsten Runde verloren.

## Weitere Runden

Plan überarbeiten, Datei neu schreiben, denselben Pane erneut fragen. Der
Prompt nennt, was sich geändert hat und mit welcher Begründung, welche
Einwände du zurückgewiesen hast und warum, und welche Entscheidungen vom
Nutzer kommen. Letzteres verhindert, dass der Reviewer eine bereits getroffene
Entscheidung in jeder Runde neu aufwirft. Dazu wieder: "Keine Wiederholung
bereits behandelter Punkte."

## Abbruch

Fertig, wenn eine Runde keine Einwände mehr liefert. Nach drei Runden
abbrechen: ein Plan, der nach drei Runden nicht steht, hat ein Problem, das
kein Review löst, und das gehört dem Nutzer vorgelegt.

Bleiben Einwände offen, die du für falsch hältst, nenne sie im Bericht
trotzdem. Der Nutzer soll sehen, wo Reviewer und du verschiedener Meinung
sind, statt nur dein Ergebnis zu lesen.

## Bericht

Pro Runde: welche Einwände kamen, welche echt waren, was du korrigiert hast,
was der Nutzer entschieden hat, was offen bleibt. Dann den überarbeiteten Plan
zur Freigabe stellen.
