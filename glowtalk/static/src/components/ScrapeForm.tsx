import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Work } from '../types';

export function ScrapeForm() {
    const [postId, setPostId] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

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

            const work: Work = await response.json();
            // Navigate to the new work's page
            navigate(`/works/${work.id}`);
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to scrape work. Please check the console for details.');
        } finally {
            setLoading(false);
        }
    };

    return (
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
    );
}
