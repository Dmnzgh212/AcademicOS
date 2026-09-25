# Zoom shared-recording acquisition research

Primary relevance: student access to **professor-shared Zoom Cloud Recording links**, not recording-owner OAuth workflows.

References reviewed during design research:
- `solo1337-del/zoom-recording-downloader`
- `georgeb3/zoom-recording-downloader`
- `ricardorodrigues-ca/zoom-recording-downloader`

## Shared-link case

The most relevant technique found uses a real browser session (for example Playwright) to open the professor-shared recording page, handle a passcode when required, and inspect the resulting playback/session state to discover recording media or transcript resources.

Useful conceptual flow:

```text
shared recording URL
 -> Playwright browser
 -> passcode/auth if required
 -> recording playback page
 -> discover transcript/media endpoint
 -> download once to local storage
 -> all later parsing happens locally
```

AcademicOS should prefer the transcript/VTT when available because it is smaller and preserves useful timing information.

## Transcript representation

Do not flatten the transcript into an untraceable summary. Preserve timestamps:

```json
{
  "lecture_id": "CEG2136-L05",
  "start": 1284.2,
  "end": 1300.7,
  "speaker": "Professor",
  "text": "..."
}
```

Later lecture alignment can map:

```text
concept
 <-> slide/page range
 <-> transcript timestamp range
 <-> personal note image
```

## Download policy

- acquire only recordings the user is authorized to access;
- download source once when practical;
- keep the original transcript/media hash;
- do not automatically upload recordings/transcripts to third-party AI services;
- local Ollama/OCR/ASR may process downloaded material;
- cloud analysis is only through explicit user action under the AcademicOS outbound policy.

## License caution

No license was found during the earlier review of `solo1337-del/zoom-recording-downloader`, so AcademicOS must treat it as a **technique reference only** and independently implement the shared-page workflow.

The other Zoom downloader projects are more useful for OAuth/account-owner scenarios and are not the default student workflow.

## Phase boundary

Zoom is intentionally later than Calendar/Brightspace events. Calendar v0.1 and announcement/deadline monitoring should work without recording access.
