// Display data for the avatar each practice side talks to (backend only sends the prompt text)

export interface Persona {
  name: string
  role: string
  mood: string
  portrait?: string
}

const PERSONAS: Record<string, Persona> = {
  applicant: { name: 'Dr. Meier', role: 'Teamleiter · Nordlicht Software (fiktiv)', mood: 'Fragt nach deinen Projekten, Entscheidungen und Erfahrungen im Team.', portrait: '/portraits/interview.png' },
  employee: { name: 'Dr. Meier', role: 'Abteilungsleiter', mood: 'Sachlich, knappes Budget, prüft jedes Argument.', portrait: '/portraits/meier.png' },
  manager: { name: 'Alex', role: 'Mitarbeiter aus deinem Team', mood: 'Fühlt sich unterbezahlt und erwartet eine Perspektive.' },
  support: { name: 'Frau Keller', role: 'Kundin', mood: 'Verärgert über ein defektes Premium-Produkt.', portrait: '/portraits/keller.png' },
  customer: { name: 'Herr Brandt', role: 'Kundenservice', mood: 'Will helfen, ist aber an Prozesse gebunden.' },
  date_lena: { name: 'Lena', role: '29, Landschaftsarchitektin aus Hamburg', mood: 'Offen, neugierig, erzählt gern von draußen.', portrait: '/portraits/lena.png' },
  date_jonas: { name: 'Jonas', role: '31, Koch aus Köln', mood: 'Locker, humorvoll, kocht leidenschaftlich.' },
}

// Fallback for sides added later: "Du bist <Name>, <Rolle>. …"
export function personaFor(sideId: string, avatarRole: string): Persona {
  const known = PERSONAS[sideId]
  if (known) return known
  const match = avatarRole.match(/^Du bist ([^,.]+)[,.]\s*([^.]*)/)
  return {
    name: match?.[1]?.trim() || 'Dein Gegenüber',
    role: match?.[2]?.trim() || '',
    mood: '',
  }
}

export function initials(name: string): string {
  const parts = name.replace(/^(Dr\.|Frau|Herr)\s+/, '').split(/\s+/).filter(Boolean)
  return parts.map(p => p[0]).join('').slice(0, 2).toUpperCase()
}
