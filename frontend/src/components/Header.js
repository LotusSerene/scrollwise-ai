import React from "react";
import { Link } from "react-router-dom";
import "./Header.css";

function Header({ isLoggedIn, onLogout }) {
  return (
    <header className="header">
      <nav>
        <ul>
          {isLoggedIn && (
            <>
              <li>
                <Link to="/create">Create</Link>
              </li>
              <li>
                <Link to="/editor">Editor</Link>
              </li>
              <li>
                <Link to="/dashboard">Dashboard</Link>
              </li>
              <li>
                <Link to="/validity">Validity</Link>
              </li>
              <li>
                <Link to="/knowledge-base">Knowledge Base</Link>
              </li>
            </>
          )}
        </ul>
      </nav>
      <div className="user-profile">
        {isLoggedIn ? (
          <div>
            <span>Welcome, User!</span>
            <button onClick={onLogout}>Logout</button>
          </div>
        ) : (
          <Link to="/login">Login</Link>
        )}
      </div>
    </header>
  );
}

export default Header;
