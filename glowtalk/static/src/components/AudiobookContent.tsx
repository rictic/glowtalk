import React, { useEffect, useRef } from "react";
import { Part } from "../types";
import "./AudiobookContent.css";

export function AudiobookContent({ audiobookId }: { audiobookId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentlyPlayingRef = useRef<Element | null>(null);

  const handleResume = (contentPieceId: string) => {
    const element = containerRef.current?.querySelector(
      `[piece-id="${contentPieceId}"]`
    ) as HTMLElement;
    if (element) {
      playAudio(element);
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

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
        if (piece.audio_file_hash) {
          pieceSpan.setAttribute("audio-file-hash", piece.audio_file_hash);
        }
        contentDiv.appendChild(pieceSpan);
      }

      partContainer.appendChild(partInfo);
      partContainer.appendChild(contentDiv);
      return partContainer;
    };

    const findNextAudioElement = (currentElement: Element | null) => {
      if (!currentElement) {
        return container.querySelector(
          "[audio-file-hash]"
        ) as HTMLElement | null;
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
      if (!hash) return;

      const contentPieceId = element.getAttribute("piece-id");
      if (contentPieceId) {
        localStorage.setItem(
          `audiobook-${audiobookId}-position`,
          contentPieceId
        );
      }

      // If clicking the currently playing element, stop playback
      if (element === currentlyPlayingRef.current) {
        audioRef.current?.pause();
        currentlyPlayingRef.current?.classList.remove("playing");
        currentlyPlayingRef.current = null;
        return;
      }

      // Remove playing class from previous element
      currentlyPlayingRef.current?.classList.remove("playing");

      // Create or reset audio element
      if (!audioRef.current) {
        audioRef.current = new Audio();
      }
      const audio = audioRef.current;

      audio.src = `/api/generated_wav_files/${hash}`;
      audio.play();

      // Update currently playing element
      currentlyPlayingRef.current = element;
      element.classList.add("playing");
      element.classList.remove("highlight");

      // Set up event listener for when audio finishes
      audio.onended = () => {
        element.classList.remove("playing");
        element.classList.remove("highlight");
        const nextElement = findNextAudioElement(element);
        if (nextElement) {
          playAudio(nextElement);
          // Only scroll if the element is not fully visible in the viewport
          const rect = nextElement.getBoundingClientRect();
          const isVisible =
            rect.top >= 0 &&
            rect.bottom <=
              (window.innerHeight || document.documentElement.clientHeight);
          if (!isVisible) {
            nextElement.scrollIntoView({ behavior: "smooth" });
          }
        } else {
          currentlyPlayingRef.current = null;
        }
      };
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

      // Remove highlight from all elements except currently playing
      container.querySelectorAll(".highlight").forEach((el) => {
        if (el !== currentlyPlayingRef.current) {
          el.classList.remove("highlight");
          el.classList.remove("cursor-pointer");
        }
      });

      if (audioElement && audioElement !== currentlyPlayingRef.current) {
        audioElement.classList.add("highlight");
        audioElement.classList.add("cursor-pointer");
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
        // This may stream megabytes of data, so we are careful to handle
        // it in chunks, and avoid doing any work over every part.
        const response = await fetch(`/api/audiobooks/${audiobookId}/content`);
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
            }
          }
        }
      } catch (error) {
        console.error("Error fetching content:", error);
      }
    };

    fetchContent();

    container.addEventListener("mousemove", handleMouseMove);
    container.addEventListener("click", handleClick);

    return () => {
      readerRef.current?.cancel();
      container.removeEventListener("mousemove", handleMouseMove);
      container.removeEventListener("click", handleClick);
      audioRef.current?.pause();
    };
  }, [audiobookId]);

  return (
    <>
      {(() => {
        const savedPosition = localStorage.getItem(
          `audiobook-${audiobookId}-position`
        );
        if (savedPosition) {
          return (
            <button
              className="resume-button"
              onClick={() => handleResume(savedPosition)}
            >
              Resume from last position
            </button>
          );
        }
        return null;
      })()}
      <div ref={containerRef} className="audiobook-content" />
    </>
  );
}
