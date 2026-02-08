import { describe, expect, test } from 'vitest';
import { createUiSentenceIdMapper, mapUiSentenceMessage, mapUiSentencePatchMessage } from '../sttService';

describe('sttService ui.sentence mapping', () => {
  test('maps ui.sentence to transcript event', () => {
    // Scenario: ui.sentence should map into a transcript event with stable segment_id.
    const getId = createUiSentenceIdMapper();
    const message = {
      id: 'sent_7',
      text: 'hello',
      label: 'spk1',
      start_ms: 100,
      end_ms: 200,
    };
    const event = mapUiSentenceMessage(message, getId);
    expect(event.type).toBe('stt.transcript');
    expect(event.text).toBe('hello');
    expect(event.speaker_label).toBe('spk1');
    expect(event.segment_id).toBe(7);
    expect(event.start_ms).toBe(100);
    expect(event.end_ms).toBe(200);
  });

  test('maps ui.sentence.patch to speaker_resolved event', () => {
    // Scenario: ui.sentence.patch should map into speaker_resolved update.
    const getId = createUiSentenceIdMapper();
    const message = { id: 'sent_x', label: 'spk2' };
    const resolved = mapUiSentencePatchMessage(message, getId);
    expect(resolved?.type).toBe('stt.speaker_resolved');
    expect(resolved?.speaker_label).toBe('spk2');
    expect(resolved?.segment_id).toBe(1);
  });

  test('maps provisional fields for ui.sentence', () => {
    const getId = createUiSentenceIdMapper();
    const message = {
      id: 'sent_9',
      text: 'hey there',
      label: 'Unknown_1',
      flags: { provisional: true },
      split_from: 'sent_8',
      speaker_color: 'unknown',
      ui_context: { provisional: true },
    };
    const event = mapUiSentenceMessage(message, getId);
    expect(event.flags?.provisional).toBe(true);
    expect(event.split_from).toBe('sent_8');
    expect(event.speaker_color).toBe('unknown');
    expect(event.ui_context).toEqual({ provisional: true });
  });

  test('maps analysis fields for ui.sentence.patch', () => {
    const getId = createUiSentenceIdMapper();
    const message = {
      id: 'sent_x',
      label: 'spk2',
      sentiment: 'Positive',
      horseman: 'None',
      level: 2,
      nudgeText: 'try to soften',
      suggestedRephrasing: 'Can we take a breath?',
      speaker_color: 'self',
      ui_context: { provisional: false },
      split_from: 'sent_y',
    };
    const resolved = mapUiSentencePatchMessage(message, getId);
    expect(resolved?.sentiment).toBe('Positive');
    expect(resolved?.horseman).toBe('None');
    expect(resolved?.level).toBe(2);
    expect(resolved?.nudgeText).toBe('try to soften');
    expect(resolved?.suggestedRephrasing).toBe('Can we take a breath?');
    expect(resolved?.speaker_color).toBe('self');
    expect(resolved?.ui_context).toEqual({ provisional: false });
    expect(resolved?.split_from).toBe('sent_y');
  });

  test('assigns new ids for split sentence suffixes', () => {
    const getId = createUiSentenceIdMapper();
    const baseId = getId('sent_5');
    const splitId = getId('sent_5_b');
    expect(splitId).not.toBe(baseId);
  });
});
