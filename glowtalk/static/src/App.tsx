import React, { useState } from 'react';
import type { Work } from './types';

export function App() {
    const [postId, setPostId] = useState('');
    const [loading, setLoading] = useState(false);
    const [work, setWork] = useState<Work | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const numericId = parseInt(postId);
        if (isNaN(numericId)) {
            alert('Please enter a valid post ID');
            return;
        }

        setLoading(true);
        try {
            const response = await fetch('/api/works/scrape_glowfic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ post_id: numericId })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setWork(data);
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to scrape work. Please check the console for details.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container">
            <h1>GlowTalk</h1>
            <p>Welcome to GlowTalk! Enter a Glowfic post ID to get started.</p>

            <form onSubmit={handleSubmit}>
                <input
                    type="text"
                    value={postId}
                    onChange={(e) => setPostId(e.target.value)}
                    placeholder="Enter post ID"
                    disabled={loading}
                />
                <button type="submit" disabled={loading}>
                    {loading ? 'Loading...' : 'Generate Audiobook'}
                </button>
            </form>

            {work && (
                <div className="work-info">
                    <h2>Work Created!</h2>
                    <p>ID: {work.id}</p>
                    <p>URL: <a href={work.url} target="_blank" rel="noopener noreferrer">{work.url}</a></p>
                    <p>Scraped: {new Date(work.scrape_date).toLocaleString()}</p>
                </div>
            )}
        </div>
    );
}
