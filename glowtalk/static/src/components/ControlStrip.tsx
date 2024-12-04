import React, { useState, useEffect } from "react";

interface ControlStripProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  progress: number; // Progress as a percentage (0 to 100)
}

export function ControlStrip({ isPlaying, onPlayPause, progress }: ControlStripProps) {
  return (
    <div className="control-strip">
      <button onClick={onPlayPause} className="play-pause-button">
        {isPlaying ? "⏸" : "▶"}
      </button>
      <div className="control-strip-progress-bar">
        <div className="control-strip-progress" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
