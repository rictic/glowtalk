import React, { useState, useEffect } from "react";

interface ControlStripProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  progress: number; // Progress as a percentage (0 to 100)
  autoScroll: boolean;
  onAutoScrollToggle: () => void;
}

export function ControlStrip({
  isPlaying,
  onPlayPause,
  progress,
  autoScroll,
  onAutoScrollToggle,
}: ControlStripProps) {
  return (
    <div className="control-strip">
      <button onClick={onPlayPause} className="play-pause-button">
        {isPlaying ? "⏸" : "▶"}
      </button>
      <div className="control-strip-progress-bar">
        <div
          className="control-strip-progress"
          style={{ width: `${progress}%` }}
        />
      </div>
      <button
        onClick={onAutoScrollToggle}
        className={`auto-scroll-button ${autoScroll ? "active" : ""}`}
        title={`Tap to ${
          autoScroll ? "disable" : "enable"
        } auto-scroll to text as its audio plays.`}
      >
        📜
      </button>
    </div>
  );
}
