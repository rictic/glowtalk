import React, { useState, useRef, useEffect } from 'react';
import type { ReferenceVoice } from '../types';
import '../styles/VoiceSelector.css';

interface VoiceSelectorProps {
    voices: ReferenceVoice[];
    selectedVoiceName: string | null | undefined;
    onSelect: (voiceName: string) => void;
    label: string;
}

export function VoiceSelector({ voices, selectedVoiceName, onSelect, label }: VoiceSelectorProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const selectedVoice = voices.find(v => v.name === selectedVoiceName);

    const playAudio = async (audioHash: string) => {
        if (playingVoiceId === audioHash) {
            // Stop currently playing audio
            audioRef.current?.pause();
            audioRef.current = null;
            setPlayingVoiceId(null);
            return;
        }

        try {
            // Stop any currently playing audio
            if (audioRef.current) {
                audioRef.current.pause();
            }

            const audio = new Audio(`/api/reference_voices/${audioHash}`);
            audioRef.current = audio;

            audio.addEventListener('ended', () => {
                setPlayingVoiceId(null);
                audioRef.current = null;
            });

            setPlayingVoiceId(audioHash);
            await audio.play();
        } catch (error) {
            console.error('Failed to play audio:', error);
            setPlayingVoiceId(null);
            audioRef.current = null;
        }
    };

    // Clean up audio on unmount
    useEffect(() => {
        return () => {
            if (audioRef.current) {
                audioRef.current.pause();
            }
        };
    }, []);

    return (
        <div className="voice-selector">
            <div className="voice-selector-header" onClick={() => setIsExpanded(!isExpanded)}>
                <span>{label}: {selectedVoice?.name || 'None selected'}</span>
                {selectedVoice && (
                    <button
                        type="button"
                        onClick={(ev) => { ev.stopPropagation(); playAudio(selectedVoice.audio_hash) }}
                        className={playingVoiceId === selectedVoice.audio_hash ? 'playing' : ''}
                    >
                        {playingVoiceId === selectedVoice.audio_hash ? 'Stop' : 'Play Sample'}
                    </button>
                )}
            </div>

            {isExpanded && (
                <div className="voice-selector-options">
                    {voices.map(voice => (
                        <div
                            key={voice.audio_hash}
                            className={`voice-option ${voice.name === selectedVoiceName ? 'selected' : ''}`}
                        >
                            <div className="voice-info">
                                <h4>{voice.name}</h4>
                                {voice.description && <p>{voice.description}</p>}
                            </div>
                            <div className="voice-actions">
                                <button
                                    type="button"
                                    onClick={() => playAudio(voice.audio_hash)}
                                    className={playingVoiceId === voice.audio_hash ? 'playing' : ''}
                                >
                                    {playingVoiceId === voice.audio_hash ? 'Stop' : 'Play Sample'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => { onSelect(voice.name);  setIsExpanded(false)}}
                                    className="select-voice"
                                >
                                    {voice.name === selectedVoiceName ? 'Selected' : 'Select'}
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
