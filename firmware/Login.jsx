import React, { useState } from 'react';
import './Login.css';
// Relative path from Login.jsx to its new home in src/assets
import backgroundVideo from './assets/background-video.mp4.mp4';
const Login = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const response = await fetch('http://localhost:8080/api/auth/authenticate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      const data = await response.json(); // Always parse JSON first

      if (!response.ok) {
        setError(response.status === 401 ? 'Invalid username or password' : (data.message || 'Login failed'));
        return;
      }

      const token = data.token || (data.data && data.data.token);
      if (token) {
        onLoginSuccess(token); // Call the callback from main.jsx
        // localStorage.setItem('token', token); // No longer needed here
        // navigate('/app'); // No longer needed here
      } else {
        setError('Login failed: No token received.');
      }
    } catch (err) {
      setError('Network error: Could not connect to server.');
    }
  };

  return (
    <div className="login-page"> {/* New outer wrapper */}
      <video autoPlay loop muted playsInline className="background-video">
        <source src={backgroundVideo} type="video/mp4" />
      </video>
    <div className="login-container">
      <div className="login-logo">
        <img src="/Logo.png" alt="EcoRoute Logo" />
      </div>
      <div className="login-card">
        
        {/* Constrained Logo Header */}
        <div className="login-logo-header">
          <img src="/Logo.png" alt="EcoRoute Logo" className="login-image" />
        </div>

        <form onSubmit={handleLogin} className="login-form">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            placeholder="test@gmail.com"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />

          <label htmlFor="password">Password</label>
          <div className="password-wrapper">
            <input
              id="password"
              type={passwordVisible ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <span 
              className="toggle-visibility" 
              onClick={() => setPasswordVisible(!passwordVisible)}
            >
              {passwordVisible ? '🙈' : '👁️'}
            </span>
          </div>

          {error && <p className="error-message">{error}</p>}

          <button type="submit" className="signin-btn">Sign In</button>
        </form>
      </div>
    </div>
    </div>
  );
};

export default Login;