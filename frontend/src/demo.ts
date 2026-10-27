import type { Analysis } from './CoachAvatar'

// Sample result for ?demo=auswertung (screenshots of the result page without a Tavus call)
export const DEMO_ANALYSIS: Analysis = {
  empathy_score: 7,
  empathy_feedback:
    'Du hast den Budgetdruck von Dr. Meier ernst genommen und nachgefragt, statt sofort zu widersprechen. Bei seinem zweiten Einwand hättest du kurz zusammenfassen können, was du gehört hast.',
  clarity_score: 8,
  clarity_feedback:
    'Deine Forderung war konkret: 8 % mehr, begründet mit dem Projekt Nordlicht und der neuen Teamverantwortung. Die Zahlen kamen früh und blieben stabil.',
  result_score: 6,
  result_feedback:
    'Ihr habt euch auf ein Folgegespräch im März geeinigt. Ein fester Termin und ein Zwischenschritt, etwa eine Einmalzahlung, hätten das Ergebnis greifbarer gemacht.',
  summary:
    'Ein sachliches, gut vorbereitetes Gespräch. Du bist mit klaren Argumenten eingestiegen und hast dich vom Budgeteinwand nicht verunsichern lassen. Am Ende hast du zu schnell akzeptiert, dass die Entscheidung vertagt wird. Beim nächsten Mal: einen konkreten Termin und eine Zwischenlösung einfordern.',
  counterpart_journey:
    'Dr. Meier war anfangs zurückhaltend und verwies auf das Budget. Als du das Projekt Nordlicht mit Zahlen belegt hast, wurde er offener und räumte ein, dass deine Rolle gewachsen ist. Zum Schluss war er bereit, sich beim Management für dich einzusetzen.',
  better_phrasings: [
    {
      original: 'Ich glaube, ich hätte vielleicht schon etwas mehr verdient.',
      better: 'Seit ich das Team Nordlicht leite, verantworte ich ein Drittel unseres Umsatzes. Deshalb möchte ich über 8 % mehr sprechen.',
      why: 'Ohne Weichmacher wirkt die Forderung selbstbewusst und ist direkt an eine Leistung gekoppelt.',
    },
    {
      original: 'Okay, dann reden wir im März nochmal.',
      better: 'Gut, dann halten wir den 12. März fest. Was müsste bis dahin passieren, damit Sie zustimmen können?',
      why: 'Ein fester Termin und eine klare Bedingung machen aus dem Vertagen einen nächsten Schritt.',
    },
  ],
}
