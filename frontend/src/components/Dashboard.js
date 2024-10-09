// Dashboard.js
import React, { useEffect, useState } from 'react';
import axios from 'axios';

const Dashboard = () => {
    const [chapters, setChapters] = useState([]);
    const [characters, setCharacters] = useState([]);

    useEffect(() => {
        fetchChapters();
        fetchCharacters();
    }, []);

    const fetchChapters = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/chapters`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setChapters(response.data.chapters);
        } catch (error) {
            console.error('Error fetching chapters:', error);
        }
    };

    const fetchCharacters = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/characters`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setCharacters(response.data.characters);
        } catch (error) {
            console.error('Error fetching characters:', error);
        }
    };

    const handleDeleteCharacter = async (id) => {
        try {
            const token = localStorage.getItem('token');
            await axios.delete(`${process.env.REACT_APP_API_URL}/api/characters/${id}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            fetchCharacters();
        } catch (error) {
            console.error('Error deleting character:', error);
        }
    };

    return (
        <div>
            <h1>Dashboard</h1>
            <h2>Current Chapters</h2>
            <ul>
                {chapters.map(chapter => (
                    <li key={chapter.id}>{chapter.title}</li>
                ))}
            </ul>
            <h2>All Characters</h2>
            <ul>
                {characters.map(character => (
                    <li key={character.id}>
                        {character.name} - {character.description}
                        <button onClick={() => handleDeleteCharacter(character.id)}>Delete</button>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default Dashboard;

