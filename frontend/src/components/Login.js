import React, { useState } from "react";
import "./Login.css";
import { useNavigate } from "react-router-dom";

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();

    try {
      console.log("Attempting login with email:", email);
      const response = await fetch(`${process.env.REACT_APP_API_URL}/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          username: email,
          password: password,
        }),
      });

      console.log("Response status:", response.status);
      const data = await response.json();
      console.log("Response data:", data);

      if (response.ok) {
        if (data.access_token && typeof data.access_token === 'string' && data.access_token.split('.').length === 3) {
          localStorage.setItem("token", data.access_token);
          console.log("Login successful with token:", data.access_token);
          onLogin(data.access_token);
          navigate("/dashboard");
        } else {
          console.error("Invalid token structure:", data.access_token);
          alert("Login failed: Invalid token received");
        }
      } else {
        console.error("Login failed with status:", response.status, "and data:", data);
        alert("Login failed: " + (data.detail || "Unknown error"));
      }
    } catch (error) {
      console.error("An error occurred during login:", error);
      alert("An error occurred during login. Please try again later.");
    }
  };

  const handleRegister = async (event) => {
    event.preventDefault();

    try {
      console.log("Attempting registration with email:", email);
      const response = await fetch(`${process.env.REACT_APP_API_URL}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username: email, password }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log("Registration successful with data:", data);
        alert("Registration successful! Please log in.");
      } else {
        const errorData = await response.json();
        console.error("Registration failed with status:", response.status, "and data:", errorData);
        if (errorData.detail === "Username already registered") {
          alert("Registration failed: User already exists");
        } else {
          alert("Registration failed: " + (errorData.detail || "Unknown error"));
        }
      }
    } catch (error) {
      console.error("An error occurred during registration:", error);
      alert("An error occurred during registration. Please try again later.");
    }
  };

  return (
    <div className="login-container">
      <h2>Login</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email">Email:</label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button type="submit">Login</button>
      </form>
      <button onClick={handleRegister}>Register</button>
    </div>
  );
}

export default Login;
