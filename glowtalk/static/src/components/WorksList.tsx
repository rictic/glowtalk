import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Work } from '../types';

export function WorksList() {
    const [works, setWorks] = useState<Work[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchWorks();
    }, []);

    const fetchWorks = async () => {
        try {
            const response = await fetch('/api/works/recent');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            setWorks(data);
        } catch (error) {
            console.error('Error fetching works:', error);
            setError('Failed to load recent works');
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div>Loading recent works...</div>;
    if (error) return <div className="error">{error}</div>;

    return (
        <div className="works-list">
            <h2>Recent Works</h2>
            {works.length === 0 ? (
                <p>No works found. Try adding one above!</p>
            ) : (
                <div className="works-grid">
                    {works.map(work => (
                        <div key={work.id} className="work-card">
                            <Link
                                to={`/works/${work.id}`}
                                className="work-title"
                            >
                                <h3>{work.title || `Glowfic #${work.id}`}</h3>
                            </Link>
                            <p>
                                <a
                                    href={work.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="external-link"
                                >
                                    View Original
                                </a>
                            </p>
                            <p className="text-sm">
                                Scraped: {new Date(work.scrape_date).toLocaleString()}
                            </p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
