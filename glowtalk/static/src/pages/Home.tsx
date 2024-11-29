import React, { useState } from 'react';
import { WorksList } from '../components/WorksList';
import { ScrapeForm } from '../components/ScrapeForm';

export function Home() {
    return (
        <>
            <h1>GlowTalk</h1>
            <p>Welcome to GlowTalk! Enter a Glowfic post ID to get started.</p>
            <ScrapeForm />
            <WorksList />
        </>
    );
} 
