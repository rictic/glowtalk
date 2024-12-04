import React, { useEffect, useRef, useState } from "react";
import { Part } from "../types";
import "./AudiobookContent.css";
import { ControlStrip } from "./ControlStrip";

export function AudiobookContent({
  audiobookId,
  numContentPieces,
}: {
  audiobookId: string;
  numContentPieces: number | null | undefined;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentlyPlayingRef = useRef<Element | null>(null);
  const [pendingResume, setPendingResume] = useState<string | null>(null);
  const pendingResumeRef = useRef<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const storedContentPieceIdx = localStorage.getItem(
    `audiobook-${audiobookId}-content-piece-idx`
  );
  const [contentPieceIdx, setContentPieceIdx] = useState(
    storedContentPieceIdx ? parseInt(storedContentPieceIdx) : 0
  );
  const [progress, setProgress] = useState(40);
  const [autoScroll, setAutoScroll] = useState(() => {
    const saved = localStorage.getItem(`auto-scroll`);
    return saved !== null ? saved === 'true' : true;
  });

  const findNextAudioElement = (currentElement: Element | null) => {
    const container = containerRef.current;
    if (!container) return null;

    if (!currentElement) {
      return container.querySelector("[audio-file-hash]") as HTMLElement | null;
    }
    let first = true;
    while (currentElement) {
      if (!first) {
        if (currentElement.getAttribute("audio-file-hash")) {
          return currentElement;
        }
      } else {
        first = false;
      }
      if (currentElement.children.length > 0) {
        currentElement = currentElement.children[0];
        continue;
      }

      while (currentElement) {
        if (currentElement.nextElementSibling) {
          currentElement = currentElement.nextElementSibling as HTMLElement;
          break;
        }
        currentElement = currentElement.parentElement as HTMLElement | null;
      }
    }
    return null;
  };

  const playAudio = (element: Element) => {
    const hash = element.getAttribute("audio-file-hash");
    const pieceIndex = element.getAttribute("piece-index");
    if (!hash || !pieceIndex) return;

    const contentPieceId = element.getAttribute("piece-id");
    if (contentPieceId) {
      localStorage.setItem(`audiobook-${audiobookId}-position`, contentPieceId);
      localStorage.setItem(
        `audiobook-${audiobookId}-content-piece-idx`,
        pieceIndex
      );
    }
    setContentPieceIdx(parseInt(pieceIndex));

    if (element === currentlyPlayingRef.current) {
      audioRef.current?.pause();
      setIsPlaying(false);
      currentlyPlayingRef.current?.classList.remove("playing");
      currentlyPlayingRef.current = null;
      return;
    }

    currentlyPlayingRef.current?.classList.remove("playing");

    if (!audioRef.current) {
      audioRef.current = new Audio();
    }
    const audio = audioRef.current;

    audio.src = `/api/generated_wav_files/${hash}`;
    audio.play();
    setIsPlaying(true);
    audio.addEventListener("pause", () => {
      setIsPlaying(false);
    });
    audio.addEventListener("play", () => {
      setIsPlaying(true);
    });

    currentlyPlayingRef.current = element;
    element.classList.add("playing");
    element.classList.remove("highlight");

    audio.onended = () => {
      element.classList.remove("playing");
      element.classList.remove("highlight");
      const nextElement = findNextAudioElement(element);
      if (nextElement) {
        playAudio(nextElement);
        const rect = nextElement.getBoundingClientRect();
        const isVisible =
          rect.top >= 0 &&
          rect.bottom <=
            (window.innerHeight || document.documentElement.clientHeight);
        if (!isVisible && autoScroll) {
          nextElement.scrollIntoView({ behavior: "smooth" });
        }
      } else {
        currentlyPlayingRef.current = null;
      }
    };
  };

  const handleResume = () => {
    const savedPosition = getSavedPosition();

    let element;
    if (savedPosition) {
      element = containerRef.current?.querySelector(
        `[piece-id="${savedPosition}"]`
      ) as HTMLElement;
    } else {
      element = findNextAudioElement(null);
    }

    if (element) {
      playAudio(element);
      element.scrollIntoView({ behavior: "smooth" });
    } else {
      setPendingResume(savedPosition);
      pendingResumeRef.current = savedPosition;
    }
  };

  const handlePlayPause = () => {
    if (isPlaying) {
      audioRef.current?.pause();
      setIsPlaying(false);
    } else {
      if (audioRef.current) {
        audioRef.current.play();
        setIsPlaying(true);
      } else {
        handleResume();
      }
    }
  };

  const handleAutoScrollToggle = () => {
    const newValue = !autoScroll;
    setAutoScroll(newValue);
    localStorage.setItem(`auto-scroll`, String(newValue));
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const abortController = new AbortController();
    let contentPieceIdx = 0;
    const createPartElement = (part: Part) => {
      const partContainer = document.createElement("div");
      partContainer.className = "part-container";

      const partInfo = document.createElement("div");
      partInfo.className = "part-info";
      partInfo.setAttribute("part-id", String(part.id));
      const announcementPiece = part.content_pieces[0];
      partInfo.setAttribute("content-piece-id", String(announcementPiece.id));
      if (announcementPiece.audio_file_hash) {
        partInfo.setAttribute(
          "audio-file-hash",
          announcementPiece.audio_file_hash
        );
        partInfo.setAttribute("piece-index", String(contentPieceIdx));
        contentPieceIdx++;
      }

      if (part.character_name) {
        const charDiv = document.createElement("div");
        charDiv.className = "part-character";
        charDiv.textContent = part.character_name;
        partInfo.appendChild(charDiv);
      }

      if (part.screenname) {
        const screenDiv = document.createElement("div");
        screenDiv.className = "part-screenname";
        screenDiv.textContent = part.screenname;
        partInfo.appendChild(screenDiv);
      }

      if (part.author_name) {
        const authorDiv = document.createElement("div");
        authorDiv.className = "part-author";
        authorDiv.textContent = part.author_name;
        partInfo.appendChild(authorDiv);
      }

      const contentDiv = document.createElement("div");
      contentDiv.className = "part-content";

      let first = true;
      for (const piece of part.content_pieces) {
        if (first) {
          first = false;
          continue;
        }
        const pieceSpan = document.createElement("span");
        pieceSpan.className = "content-piece";
        pieceSpan.textContent = " " + piece.text;
        pieceSpan.setAttribute("piece-id", String(piece.id));
        pieceSpan.setAttribute("piece-index", String(contentPieceIdx));
        contentPieceIdx++;
        if (piece.audio_file_hash) {
          pieceSpan.setAttribute("audio-file-hash", piece.audio_file_hash);
        }
        contentDiv.appendChild(pieceSpan);
      }

      partContainer.appendChild(partInfo);
      partContainer.appendChild(contentDiv);
      return partContainer;
    };

    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const audioElement = target.closest("[audio-file-hash]") as HTMLElement;
      if (audioElement) {
        playAudio(audioElement);
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const audioElement = target.closest("[audio-file-hash]");

      container.querySelectorAll(".highlight").forEach((el) => {
        if (el !== currentlyPlayingRef.current) {
          el.classList.remove("highlight");
        }
      });

      if (audioElement && audioElement !== currentlyPlayingRef.current) {
        audioElement.classList.add("highlight");
      }
    };

    const fetchContent = async () => {
      if (!container) {
        return;
      }
      while (container.childNodes.length > 0) {
        container.removeChild(container.childNodes[0]);
      }
      const ourContainer = document.createElement("div");
      container.appendChild(ourContainer);
      try {
        const response = await fetch(`/api/audiobooks/${audiobookId}/content`, {
          signal: abortController.signal,
        });
        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        readerRef.current = reader;
        const decoder = new TextDecoder();

        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.trim()) {
              const part = JSON.parse(line);
              const element = createPartElement(part);
              ourContainer.appendChild(element);

              if (pendingResumeRef.current) {
                const pendingElement = element.querySelector(
                  `[piece-id="${pendingResumeRef.current}"]`
                ) as HTMLElement;
                if (pendingElement) {
                  playAudio(pendingElement);
                  pendingElement.scrollIntoView({ behavior: "smooth" });
                  setPendingResume(null);
                  pendingResumeRef.current = null;
                }
              }
            }
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          // expected
        } else {
          console.error("Error fetching content:", error);
        }
      }
    };

    fetchContent();

    container.addEventListener("mousemove", handleMouseMove);
    container.addEventListener("click", handleClick);

    return () => {
      abortController.abort();
      readerRef.current?.cancel();
      container.removeEventListener("mousemove", handleMouseMove);
      container.removeEventListener("click", handleClick);
      audioRef.current?.pause();
    };
  }, [audiobookId]);

  useEffect(() => {
    if (numContentPieces == null) {
      setProgress(0); // dunno
      return;
    }
    const progress = Math.round((contentPieceIdx / numContentPieces) * 100);
    setProgress(progress);
  }, [contentPieceIdx, numContentPieces]);

  const getSavedPosition = () => {
    return localStorage.getItem(`audiobook-${audiobookId}-position`);
  };

  return (
    <>
      <div ref={containerRef} className="audiobook-content" />
      <ControlStrip
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        progress={progress}
        autoScroll={autoScroll}
        onAutoScrollToggle={handleAutoScrollToggle}
      />
    </>
  );
}
