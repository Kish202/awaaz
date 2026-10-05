// Static facts about each language, used for the hero and dataset overview.
// Common Voice numbers are from the 26.0 release (June 2026).

export const LANGUAGES = [
  {
    code: 'gju',
    name: 'Gojri',
    native: 'گوجری',
    iso: 'ISO 639-3 gju',
    region: 'Jammu & Kashmir · Northern Pakistan · Afghanistan',
    community: 'Gujjar community',
    commonVoice: { hours: 10.67, validated: 10.07, speakers: 7, sentences: 3854, clips: 11741 },
    note: 'Seven speakers. Any model will overfit speaker identity until the pool grows.',
    sample: 'میں گھر جا رہا ہوں۔',
  },
  {
    code: 'phr',
    name: 'Pahari-Pothwari',
    native: 'پہاڑی پوٹھواری',
    iso: 'ISO 639-3 phr',
    region: 'Pothohar Plateau · Azad Jammu & Kashmir · Poonch',
    community: 'Pahari and Pothwari speakers',
    commonVoice: { hours: 14.11, validated: 13.97, speakers: 63, sentences: 2077, clips: 12825 },
    note: 'Only 2,077 unique sentences. Sentences, not volunteers, are the bottleneck.',
    sample: 'تم کہاں ہو؟',
  },
]

export const REASON_LABELS = {
  too_short: 'Too short',
  too_long: 'Too long',
  digits: 'Contains digits',
  latin: 'Latin letters',
  foreign_char: 'Foreign script',
  url: 'URL or handle',
  abbreviation: 'Abbreviation',
  repeat_chars: 'Repeated characters',
  empty: 'Empty',
}

export function byCode(code) {
  return LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0]
}
