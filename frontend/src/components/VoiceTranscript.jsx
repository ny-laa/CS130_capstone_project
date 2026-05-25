export default function VoiceTranscript({ transcript, duration }) {
  return (
    <div className="voice-transcript">
      <div className="transcript-header">
        <span className="transcript-icon">Voice call</span>
        {duration && <span className="transcript-duration">{duration}</span>}
      </div>
      <div className="transcript-lines">
        {transcript.map((line, i) => (
          <div key={i} className="transcript-line">
            <span className="transcript-time">{line.time}</span>
            <span className={`transcript-speaker transcript-speaker--${line.speaker.toLowerCase()}`}>
              {line.speaker}
            </span>
            <span className="transcript-text">{line.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
