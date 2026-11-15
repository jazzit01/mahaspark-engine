import {BulletinProps} from './types';

/** Studio-only sample (the real bulletin comes from public/bulletin.json). Audio points at an existing file. */
const item = (headline: string, context: string, start: number) => ({
  category: 'पुणे',
  headline,
  context,
  audio: 'whoosh.wav',
  seconds: 10,
  start,
  lead_seconds: 0.5,
  photo: null,
});

export const sampleBulletin: BulletinProps = {
  items: [
    item('पुण्यात बुधवारी पाणीपुरवठा बंद', 'महापालिकेच्या देखभाल कामामुळे ८५% भागात परिणाम होणार', 0),
    item('राज्यात आज मुसळधार पावसाचा इशारा', 'हवामान विभागाने कोकण आणि घाटमाथ्यावर ऑरेंज अलर्ट दिला', 10),
    item('मेट्रो विस्तारास केंद्राची मंजुरी', 'नव्या मार्गासाठी १,२०० कोटी रुपयांचा खर्च अपेक्षित', 20),
  ],
  outro_seconds: 8,
  outro_start: 30,
  total_seconds: 38,
  credits: [],
};
