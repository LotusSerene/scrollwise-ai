import React, { useState, useEffect } from "react";
import { Route, Routes, Navigate } from "react-router-dom";
import Header from "./components/Header";
import Login from "./components/Login";
import Editor from "./components/Editor";
import Create from "./components/Create";
import Dashboard from "./components/Dashboard";
import Validity from "./components/Validity";
import KnowledgeBase from "./components/KnowledgeBase";
import "./App.css";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [chapters, setChapters] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setIsLoggedIn(true);
    } else {
      setIsLoggedIn(false);
    }
  }, []);

  const handleLogin = (token) => {
    localStorage.setItem("token", token);
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setIsLoggedIn(false);
  };

  const onChapterGenerated = (newChapter) => {
    setChapters((prevChapters) => [...prevChapters, newChapter]);
  };

  return (
    <div className="App">
      <Header isLoggedIn={isLoggedIn} onLogout={handleLogout} />
      <main>
        <Routes>
          <Route path="/login" element={isLoggedIn ? <Navigate to="/dashboard" /> : <Login onLogin={handleLogin} />} />
          <Route
            path="/create"
            element={isLoggedIn ? <Create onChapterGenerated={onChapterGenerated} /> : <Navigate to="/login" />}
          />
          <Route
            path="/editor"
            element={isLoggedIn ? <Editor chapters={chapters} setChapters={setChapters} /> : <Navigate to="/login" />}
          />
          <Route
            path="/validity"
            element={isLoggedIn ? <Validity /> : <Navigate to="/login" />}
          />
          <Route
            path="/dashboard"
            element={isLoggedIn ? <Dashboard chapters={chapters} /> : <Navigate to="/login" />}
          />
          <Route
            path="/knowledge-base"
            element={isLoggedIn ? <KnowledgeBase /> : <Navigate to="/login" />}
          />
          <Route
            path="/"
            element={isLoggedIn ? <Navigate to="/dashboard" /> : <Navigate to="/login" />}
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;
