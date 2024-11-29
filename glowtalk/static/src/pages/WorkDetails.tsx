import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { Work, Audiobook } from '../types';

export function WorkDetails() {
    const { workId } = useParams();
    const navigate = useNavigate();
    const [work, setWork] = useState<Work | null>(null);
    const [audiobooks, setAudiobooks] = useState<Audiobook[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchWorkDetails();
    }, [workId]);

    const fetchWorkDetails = async () => {
        try {
            const response = await fetch(`/api/works/${workId}`);
            if (!response.ok) throw new Error('Failed to fetch work details');
            const workData = await response.json();
            setWork(workData);

            // Fetch audiobooks for this work
            const audiobooksResponse = await fetch(`/api/works/${workId}/audiobooks`);
            if (!audiobooksResponse.ok) throw new Error('Failed to fetch audiobooks');
            const audiobooksData = await audiobooksResponse.json();
            setAudiobooks(audiobooksData);
        } catch (error) {
            console.error('Error:', error);
            setError('Failed to load work details');
        } finally {
            setLoading(false);
        }
    };

    const createAudiobook = async () => {
        try {
            const response = await fetch(`/api/works/${workId}/audiobooks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    description: `Audiobook for ${work?.title || 'Untitled Work'}`
                })
            });
            if (!response.ok) throw new Error('Failed to create audiobook');
            const newAudiobook = await response.json();
            setAudiobooks([...audiobooks, newAudiobook]);
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to create audiobook');
        }
    };

    if (loading) return <div>Loading...</div>;
    if (error) return <div className="error">{error}</div>;
    if (!work) return <div>Work not found</div>;

    return (
        <div>
            <button className="back-button" onClick={() => navigate('/')}>
                ← Back to Works
            </button>

            <h1>{work.title || `Glowfic #${work.id}`}</h1>
            <p>
                <a href={work.url} target="_blank" rel="noopener noreferrer">
                    View Original Post
                </a>
            </p>
            <p>Scraped: {new Date(work.scrape_date).toLocaleString()}</p>

            <div className="audiobooks-section">
                <h2>Audiobooks</h2>
                {audiobooks.length === 0 ? (
                    <p>No audiobooks yet.</p>
                ) : (
                    <div className="audiobooks-grid">
                        {audiobooks.map(audiobook => (
                            <div key={audiobook.id} className="audiobook-card">
                                <h3>Audiobook #{audiobook.id}</h3>
                                {audiobook.description && (
                                    <p>{audiobook.description}</p>
                                )}
                                <p>Created: {new Date(audiobook.created_at).toLocaleString()}</p>
                                <a
                                    href={`/api/audiobooks/${audiobook.id}/mp3`}
                                    download={`${work.title || `Glowfic ${work.id}`}.mp3`}
                                    className="button-like-link"
                                >
                                    Download MP3
                                </a>
                            </div>
                        ))}
                    </div>
                )}

                <button className="create-button" onClick={createAudiobook}>
                    Create New Audiobook
                </button>
            </div>
        </div>
    );
}
