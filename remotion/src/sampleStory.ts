import {Story, ThemeName} from './types';

/**
 * Placeholder story for Remotion Studio previews only (no voiceover; word times are spread evenly).
 * The real pipeline overrides every prop with remotion/public/story.json.
 */
const SCENES = [
  {
    headline: 'पुणे महापालिकेची मोठी घोषणा',
    description: 'शहरातील नव्या उड्डाणपुलाच्या कामाला अंतिम मंजुरी मिळाली आहे.',
    tts_text: 'पुणे महापालिकेने, शहरातील नव्या उड्डाणपुलाला अंतिम मंजुरी दिली आहे.',
    motion: {type: 'place' as const, value: 'पुणे'},
  },
  {
    headline: 'काम पुढील महिन्यात सुरू होणार',
    description: 'प्रकल्पासाठी 120 कोटी रुपयांची तरतूद करण्यात आली आहे.',
    tts_text: 'प्रकल्पासाठी, एकशे वीस कोटी रुपयांची तरतूद करण्यात आली आहे.',
    motion: {type: 'stat' as const, value: '₹120 कोटी', label: 'मंजूर निधी'},
  },
  {
    headline: 'वाहतूक कोंडीतून नागरिकांना दिलासा',
    description: 'दोन वर्षांत उड्डाणपूल वाहतुकीसाठी खुला होईल, असे आयुक्तांनी सांगितले.',
    tts_text: 'दोन वर्षांत, उड्डाणपूल वाहतुकीसाठी खुला होईल, असे आयुक्तांनी सांगितले.',
    motion: {type: 'quote' as const, value: 'दोन वर्षांत उड्डाणपूल खुला होईल.', label: 'महापालिका आयुक्त'},
  },
];

export const buildSampleStory = (theme: ThemeName): Story => {
  const words: Story['words'] = [];
  let cursor = 0.4;
  const scenes = SCENES.map((scene, sceneIndex) => {
    const tokens = scene.tts_text.split(' ');
    const sceneStart = sceneIndex === 0 ? 0 : cursor;
    tokens.forEach((text) => {
      const length = 0.28 + text.length * 0.035;
      words.push({text, start: Number(cursor.toFixed(3)), end: Number((cursor + length).toFixed(3)), scene: sceneIndex});
      cursor += length;
    });
    cursor += 0.35;
    return {...scene, start: sceneStart, end: cursor};
  });

  return {
    category: 'पुणे',
    visual_theme: theme,
    audio_mood: 'neutral',
    scenes,
    words,
    duration_seconds: Number(cursor.toFixed(3)),
    audio: false,
  };
};
