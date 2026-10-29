import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.VITE_API_HOST ? `https://${import.meta.env.VITE_API_HOST}` : "");

function playCompletionAlert() {
  if ("vibrate" in navigator) navigator.vibrate([500, 180, 500, 180, 700, 180, 900]);
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  const context = new AudioContext();
  [0, 0.22, 0.44].forEach((offset) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, context.currentTime + offset);
    gain.gain.exponentialRampToValueAtTime(0.22, context.currentTime + offset + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + offset + 0.16);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(context.currentTime + offset);
    oscillator.stop(context.currentTime + offset + 0.18);
  });
  window.setTimeout(() => context.close(), 900);
}

function Timer({ seconds, onFinish }) {
  const [remaining, setRemaining] = useState(seconds);
  const finishedRef = useRef(false);
  useEffect(() => {
    if (remaining <= 0 && !finishedRef.current) {
      finishedRef.current = true;
      onFinish();
      playCompletionAlert();
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("TimeSense timer finished");
      }
      return undefined;
    }
    const timer = setInterval(() => setRemaining((value) => value - 1), 1000);
    return () => clearInterval(timer);
  }, [remaining, onFinish]);
  return <div className="timer">{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}</div>;
}

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(null);
  const [timeUp, setTimeUp] = useState(false);
  const [extensionUsed, setExtensionUsed] = useState(false);
  const [actualMinutes, setActualMinutes] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [feedbackSaved, setFeedbackSaved] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [taskIntent, setTaskIntent] = useState("");
  const [taskDetails, setTaskDetails] = useState("");
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    const splash = document.getElementById("initial-splash");
    if (!splash) return undefined;
    const hideTimer = window.setTimeout(() => {
      splash.classList.add("splash-hidden");
      window.setTimeout(() => splash.remove(), 400);
    }, 350);
    return () => window.clearTimeout(hideTimer);
  }, []);

  const chooseFile = (event) => {
    setFile(event.target.files?.[0] || null);
    setError("");
  };

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("Camera access requires HTTPS or localhost in your browser.");
      return;
    }
    try {
      setCameraError("");
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
      setCameraOpen(true);
    } catch {
      setCameraError("Camera access was unavailable. Allow camera permission or upload a file instead.");
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraOpen(false);
  };

  const capture = () => {
    if (!videoRef.current?.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext("2d").drawImage(videoRef.current, 0, 0);
    canvas.toBlob((blob) => setFile(new File([blob], "camera-capture.jpg", { type: "image/jpeg" })), "image/jpeg");
    stopCamera();
  };

  const analyze = async () => {
    if (!file) return;
    setError("");
    setIsAnalyzing(true);
    if ("Notification" in window && Notification.permission === "default") {
      await Notification.requestPermission();
    }
    const body = new FormData();
    body.append("file", file);
    body.append("task_intent", taskIntent.trim());
    body.append("task_details", taskDetails.trim());
    try {
      const response = await fetch(`${API_URL}/api/analyze`, { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Analysis failed.");
      setResult(payload);
      setTimeUp(false);
      setExtensionUsed(false);
      setActualMinutes("");
      const timerResponse = await fetch(`${API_URL}/api/timer/start`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estimated_minutes: payload.estimated_minutes, task_id: payload.task_id }),
      });
      const timer = await timerResponse.json();
      setTimerSeconds(timer.duration_seconds);
    } catch (requestError) {
      setError(requestError instanceof TypeError
        ? "Could not connect to TimeSense. Make sure the backend is running on port 8000."
        : requestError.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const addFiveMinutes = () => {
    if (!result || extensionUsed) return;
    setTimerSeconds(5 * 60);
    setTimeUp(false);
    setExtensionUsed(true);
    setActualMinutes(String(result.estimated_minutes + 5));
  };

  const submitFeedback = async () => {
    if (!result?.task_id || !actualMinutes) return;
    const response = await fetch(`${API_URL}/api/feedback`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: result.task_id, actual_minutes: Number(actualMinutes) }),
    });
    if (!response.ok) setError("Could not save feedback.");
    else {
      setActualMinutes("");
      setFeedbackSaved(true);
    }
  };

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);
  useEffect(() => {
    if (cameraOpen && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [cameraOpen]);

  return <main className="app-shell">
    <header className="topbar">
      <a className="brand" href="/">
        <span className="brand-mark">TS</span>
        <span>TimeSense</span>
      </a>
      <span className="status-pill"><span className="status-dot" /> AI time planner</span>
    </header>
    {result && <div className="session-bar">
      <div className="session-file"><span className="session-icon">✓</span><div><strong>{file?.name || "Your task"}</strong><small>{result.category.replace("_", " ")} · {result.estimated_minutes} min estimate</small></div></div>
      {timerSeconds !== null && <div className="session-timer"><span>FOCUSING</span><Timer seconds={timerSeconds} onFinish={() => { setTimerSeconds(null); setTimeUp(true); }} /></div>}
    </div>}

    <section className="hero">
      <div className="eyebrow">FOCUS WITH CONFIDENCE</div>
      <h1>Turn any task into<br /><em>time well spent.</em></h1>
      <p>Show us what you want to work on. TimeSense uses the image and your goal to create a realistic focus estimate.</p>
    </section>

    <section className="workspace-grid">
      <div className="card upload-card">
        <div className="card-heading">
          <div><span className="step-number">01</span><h2>Share your task</h2></div>
          <span className="format-hint">PDF · JPG · PNG</span>
        </div>
        <label className="drop-zone">
          <input type="file" accept=".pdf,image/jpeg,image/png,image/webp" onChange={chooseFile} />
          <span className="upload-icon">↑</span>
          <strong>{file ? file.name : "Drop a file here"}</strong>
          <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB ready` : "or click to browse your device"}</span>
        </label>
        <div className="divider"><span>OR</span></div>
        <button className="secondary-button camera-button" onClick={startCamera}><span>◎</span> Use camera</button>
        {cameraError && <p className="camera-error">{cameraError}</p>}
        {cameraOpen && <div className="camera-panel">
          <video ref={videoRef} autoPlay muted playsInline />
          <div className="camera-actions">
            <button className="primary-button" onClick={capture}>Capture photo</button>
            <button className="secondary-button" onClick={stopCamera}>Cancel</button>
          </div>
        </div>}
        <div className="intent-box">
          <div className="intent-heading"><span className="step-number">02</span><div><h2>What would you like to do?</h2><p>Tell us your goal so the estimate fits your task.</p></div></div>
          <label className="field-label">Your goal <span>required</span>
            <input value={taskIntent} onChange={(event) => setTaskIntent(event.target.value)} placeholder="e.g. I want to clean my room" maxLength="500" />
          </label>
          <label className="field-label">Any useful details? <span>optional</span>
            <textarea value={taskDetails} onChange={(event) => setTaskDetails(event.target.value)} placeholder="e.g. Focus on the desk, floor, and clothes. I have 45 minutes." rows="3" maxLength="1000" />
          </label>
        </div>
        <button className="primary-button analyze-button" disabled={!file || taskIntent.trim().length < 3 || isAnalyzing} onClick={analyze}>
          {isAnalyzing ? <><span className="spinner" /> Reading your task...</> : <>Analyze & start timer <span>→</span></>}
        </button>
        <p className="privacy-note">✦ Your file is processed securely and never shared.</p>
      </div>

      <div className="card guide-card">
        <span className="step-number">HOW IT WORKS</span>
        <h2>From upload<br />to done.</h2>
        <div className="guide-step"><span>1</span><div><strong>Understand</strong><small>Gemini reads the details</small></div></div>
        <div className="guide-line" />
        <div className="guide-step"><span>2</span><div><strong>Estimate</strong><small>Get a realistic time range</small></div></div>
        <div className="guide-line" />
        <div className="guide-step"><span>3</span><div><strong>Focus</strong><small>Start your timer and begin</small></div></div>
      </div>
    </section>

    {error && <div className="alert error"><span>!</span>{error}</div>}
    {result && <section className="result-layout">
      <div className="card result-card">
        <div className="result-topline"><span className="category-label">{result.category.replace("_", " ")}</span><span className="confidence">Confidence {Math.round(result.confidence * 100)}%</span></div>
        <h2>{result.summary}</h2>
        <div className="estimate-block"><span className="estimate-label">ESTIMATED FOCUS TIME</span><strong>{result.estimated_minutes}<small> min</small></strong><span className="range">Likely range: {result.range_low}–{result.range_high} minutes</span></div>
        {timerSeconds !== null && <div className="timer-panel"><div className="timer-label">FOCUS TIMER</div><p className="timer-active">Your focus timer is active above.</p><span>Stay with it. You’ve got this.</span></div>}
        {timeUp && <div className="time-up-panel">
          <div className="time-up-kicker">TIMER COMPLETE</div>
          <h3>Time’s up!</h3>
          <p>Your focus session has ended. Record your actual time or keep going if you need to.</p>
          {!extensionUsed && <button className="primary-button" onClick={addFiveMinutes}>Need more time? Set 5 more minutes</button>}
          {extensionUsed && <span className="extension-note">Your extra 5 minutes are included in the feedback below.</span>}
        </div>}
      </div>
      <div className="card feedback-card">
        <span className="step-number">AFTER YOU FINISH</span><h2>Help us tune<br />your next estimate.</h2>
        <label>{extensionUsed ? "How many minutes did it take? (minimum shown includes your extra 5 minutes)" : "How many minutes did it take?"} <input type="number" min="1" value={actualMinutes} onChange={(event) => setActualMinutes(event.target.value)} placeholder="e.g. 25" /></label>
        <button className="secondary-button" onClick={submitFeedback}>Save feedback <span>→</span></button>
        {feedbackSaved && <p className="success">✓ Feedback saved. Future estimates will be more personal.</p>}
      </div>
    </section>}
    <footer><span>TimeSense</span><span>Built for better focus · Powered by Gemini</span></footer>
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
