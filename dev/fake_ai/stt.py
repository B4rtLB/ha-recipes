from homeassistant.components import stt
async def async_setup_entry(hass, entry, add):
    add([FakeSTT()])
class FakeSTT(stt.SpeechToTextEntity):
    _attr_name = "Fake STT"
    _attr_unique_id = "fake_stt"
    supported_languages = ["en", "nl"]
    supported_formats = [stt.AudioFormats.OGG, stt.AudioFormats.WAV]
    supported_codecs = [stt.AudioCodecs.OPUS, stt.AudioCodecs.PCM]
    supported_bit_rates = [stt.AudioBitRates.BITRATE_16]
    supported_sample_rates = [stt.AudioSampleRates.SAMPLERATE_16000]
    supported_channels = [stt.AudioChannels.CHANNEL_MONO]
    async def async_process_audio_stream(self, metadata, stream):
        n = 0
        async for c in stream: n += len(c)
        self.hass.data["fake_ai_last"]["stt_bytes"] = n
        return stt.SpeechResult("spoken: two cups of rice", stt.SpeechResultState.SUCCESS)
