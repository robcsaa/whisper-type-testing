# Test Phrases
These phrases are for TESTING ONLY. They should NEVER be used for training the model.

**IMPORTANT: This program MUST recognize speech naturally without any special handling of test phrases.**
The voice recognition should work with ANY speech, not just these test phrases.

1. "check one two three four five"
2. "hello world"
3. "buffer overflow"

## Notes
- Uses PipeWire or ALC245 for audio input
- Audio processed at 16kHz
- Ctrl+Alt+V to start/stop
- Text appears at cursor position 
- Uses general speech recognition, not trained on specific phrases
- Only applies basic spell check, no test phrase matching

## Development Guidelines
- NEVER add code that specifically recognizes the test phrases
- NEVER force any recognition to match test phrases
- DO NOT add special rules for these test phrases
- Speech recognition MUST work for general text, not just these phrases
- Use standard spell checking only 