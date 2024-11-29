import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import type { Work, AudiobookDetail, ReferenceVoice } from '../types';

export function AudiobookDetails() {
    const { audiobookId } = useParams();
    const [audiobook, setAudiobook] = useState<AudiobookDetail | null>(null);
    const [work, setWork] = useState<Work | null>(null);
    const [referenceVoices, setReferenceVoices] = useState<ReferenceVoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchData();
    }, [audiobookId]);

    const fetchData = async () => {
        try {
            // Fetch audiobook details
            const audiobookResponse = await fetch(`/api/audiobooks/${audiobookId}/details`);
            if (!audiobookResponse.ok) throw new Error('Failed to fetch audiobook details');
            const audiobookData = await audiobookResponse.json();
            setAudiobook(audiobookData);

            // Fetch work details
            const workResponse = await fetch(`/api/works/${audiobookData.original_work_id}`);
            if (!workResponse.ok) throw new Error('Failed to fetch work details');
            const workData = await workResponse.json();
            setWork(workData);

            // Fetch available reference voices
            const referenceVoicesResponse = await fetch('/api/reference_voices');
            if (!referenceVoicesResponse.ok) throw new Error('Failed to fetch reference voices');
            const referenceVoicesData = await referenceVoicesResponse.json();
            setReferenceVoices(referenceVoicesData);

        } catch (error) {
            console.error('Error:', error);
            setError('Failed to load audiobook details');
        } finally {
            setLoading(false);
        }
    };

    const updateDefaultSpeaker = async (speakerId: number) => {
        try {
            const response = await fetch(`/api/audiobooks/${audiobookId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ default_speaker_id: speakerId })
            });
            if (!response.ok) throw new Error('Failed to update default speaker');
            const updatedAudiobook = await response.json();
            setAudiobook(prev => prev ? { ...prev, ...updatedAudiobook } : null);
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to update default speaker');
        }
    };

    const updateCharacterVoice = async (characterName: string, speakerId: number | null) => {
        try {
            const response = await fetch(`/api/audiobooks/${audiobookId}/character-voices`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    character_name: characterName,
                    speaker_id: speakerId
                })
            });
            if (!response.ok) throw new Error('Failed to update character voice');
            await fetchData(); // Refresh data
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to update character voice');
        }
    };

    if (loading) return <div>Loading...</div>;
    if (error) return <div className="error">{error}</div>;
    if (!audiobook || !work) return <div>Audiobook not found</div>;

    return (
        <div className="audiobook-details">
            <Link to={`/works/${work.id}`} className="back-link">
                ← Back to Work
            </Link>

            <h1>{work.title || `Glowfic #${work.id}`} - Audiobook</h1>

            <section className="voice-settings">
                <h2>Voice Settings</h2>

                <div className="default-voice">
                    <h3>Default Voice</h3>
                    <select
                        value={audiobook.default_speaker_id || ''}
                        onChange={(e) => updateDefaultSpeaker(Number(e.target.value))}
                    >
                        <option value="">Select a default voice</option>
                        {referenceVoices.map(voice => (
                            <option key={voice.audio_hash} value={voice.audio_hash}>
                                {voice.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="character-voices">
                    <h3>Character Voices</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Character</th>
                                <th>Speaker</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {audiobook.characters.map(character => (
                                <tr key={character.character_name}>
                                    <td>{character.character_name}</td>
                                    <td>
                                        <select
                                            value={character.speaker_id || ''}
                                            onChange={(e) => updateCharacterVoice(character.character_name, Number(e.target.value))}
                                        >
                                            <option value="">Select a speaker</option>
                                            {referenceVoices.map(voice => (
                                                <option key={voice.audio_hash} value={voice.audio_hash}>
                                                    {voice.name}
                                                </option>
                                            ))}
                                        </select>
                                    </td>
                                    <td>
                                        <button onClick={() => updateCharacterVoice(character.character_name, character.speaker_id)}>
                                            Update
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}
