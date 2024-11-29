import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Home } from './pages/Home';
import { WorkDetails } from './pages/WorkDetails';

export function App() {
    return (
        <BrowserRouter>
            <div className="container">
                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/works/:workId" element={<WorkDetails />} />
                </Routes>
            </div>
        </BrowserRouter>
    );
}
