from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from app.chat_manager import manager
from app.database import init_db, save_message, get_group_history, create_group, verify_group, clear_group_messages, create_user, verify_user, DB_NAME
import secrets
import hashlib
import aiosqlite

app = FastAPI()
active_tokens = {}

SERVER_SECRET = "cn_chat_super_secret_salt_2026"

def get_dm_password(u1: str, u2: str) -> str:
    users = sorted([u1, u2])
    raw = f"{users[0]}_{users[1]}_{SERVER_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()

@app.on_event("startup")
async def startup_event():
    await init_db()

html = """
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">  
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>sechat</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #7c3aed; /* Purple */
                --primary-hover: #6d28d9;
                --bg-sidebar: #ffffff;
                --bg-chat: #f0f2f5;
                --bg-navbar: #ffffff;
                --text-main: #1e293b;
                --text-muted: #64748b;
                --border: #e2e8f0;
                --white: #ffffff;
                --hover-bg: #f8fafc;
                --active-bg: #f1f5f9;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
            body { 
                background-color: var(--bg-chat);
                color: var(--text-main);
                height: 100vh;
                overflow: hidden;
                display: flex;
                flex-direction: column;
            }

            /* --- GLOBAL AUTH MODAL --- */
            #global-auth-section {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.6);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 2000;
            }
            .auth-box {
                width: 100%;
                max-width: 400px;
                background: var(--white);
                border-radius: 16px;
                padding: 32px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            }
            .auth-box h1 { font-size: 1.6rem; font-weight: 700; color: var(--primary); text-align: center; margin-bottom: 6px; }
            .auth-box p { font-size: 0.85rem; color: var(--text-muted); text-align: center; margin-bottom: 24px; }
            .tabs { display: flex; background: var(--bg-chat); padding: 4px; border-radius: 10px; margin-bottom: 20px; }
            .tab { flex: 1; padding: 10px; text-align: center; cursor: pointer; font-weight: 600; font-size: 0.85rem; color: var(--text-muted); border-radius: 8px; transition: all 0.2s; }
            .tab.active { background: var(--white); color: var(--primary); box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            
            /* FORMS */
            .input-group { margin-bottom: 16px; }
            .input-group label { display: block; font-size: 0.8rem; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
            input { width: 100%; padding: 12px 14px; background: var(--white); border: 1px solid var(--border); border-radius: 8px; color: var(--text-main); font-size: 0.95rem; outline: none; transition: border-color 0.2s; }
            input:focus { border-color: var(--primary); }
            button.btn-submit { width: 100%; padding: 12px; background: var(--primary); color: white; border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; margin-top: 8px; transition: background 0.2s; }
            button.btn-submit:hover { background: var(--primary-hover); }
            .status { font-size: 0.85rem; margin-top: 12px; text-align: center; }

            /* --- TOP NAVBAR --- */
            .navbar {
                display: none; /* hidden until logged in */
                height: 60px;
                background: var(--bg-navbar);
                border-bottom: 1px solid var(--border);
                align-items: center;
                justify-content: space-between;
                padding: 0 24px;
                z-index: 100;
            }
            .navbar .nav-left { font-size: 1.4rem; font-weight: 700; color: var(--primary); }
            .navbar .nav-right { display: flex; align-items: center; gap: 16px; }
            .navbar .nav-right span { font-size: 0.9rem; color: var(--text-muted); font-weight: 500; }
            .navbar .nav-right strong { color: var(--text-main); }
            .btn-outline { padding: 8px 16px; background: transparent; border: 1px solid var(--border); border-radius: 20px; font-size: 0.85rem; font-weight: 600; color: var(--text-main); cursor: pointer; transition: all 0.2s; }
            .btn-outline:hover { background: var(--hover-bg); border-color: #cbd5e1; }
            .btn-logout { border-color: #fca5a5; color: #ef4444; }
            .btn-logout:hover { background: #fef2f2; border-color: #ef4444; color: #dc2626; }
            .btn-leave-chat { background: transparent; border: none; color: var(--text-muted); font-size: 1.25rem; line-height: 1; cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: all 0.2s; }
            .btn-leave-chat:hover { background: #fef2f2; color: #ef4444; }

            /* --- APP LAYOUT (SPLIT PANE) --- */
            #app-container {
                display: none; /* hidden until logged in */
                flex: 1;
                width: 100%;
                overflow: hidden;
            }
            
            /* SIDEBAR */
            .sidebar {
                width: 320px;
                background: var(--bg-sidebar);
                border-right: 1px solid var(--border);
                display: flex;
                flex-direction: column;
                z-index: 10;
            }
            .sidebar-header {
                padding: 20px 20px 12px 20px;
            }
            .sidebar-header h2 { font-size: 1.3rem; color: var(--text-main); }
            
            .sidebar-content {
                flex: 1;
                overflow-y: auto;
            }
            /* Chat List Item */
            .chat-item {
                display: flex;
                align-items: center;
                padding: 14px 20px;
                cursor: pointer;
                border-bottom: 1px solid #f1f5f9;
                transition: background 0.15s;
            }
            .chat-item:hover { background: var(--hover-bg); }
            .chat-item.active { background: var(--active-bg); }
            
            .chat-avatar {
                width: 48px;
                height: 48px;
                border-radius: 50%;
                background: #e2e8f0;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.2rem;
                font-weight: 700;
                color: #94a3b8;
                margin-right: 14px;
            }
            .chat-item.active .chat-avatar { background: var(--primary); color: white; }
            
            .chat-info { flex: 1; overflow: hidden; display: flex; align-items: center; justify-content: space-between; }
            .chat-title-group { flex: 1; overflow: hidden; }
            .chat-title-group h4 { font-size: 1rem; color: var(--text-main); margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .chat-title-group p { font-size: 0.8rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            
            .unread-badge {
                background: #ef4444;
                color: white;
                font-size: 0.75rem;
                font-weight: 700;
                min-width: 22px;
                height: 22px;
                border-radius: 11px;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 0 6px;
                margin-left: 8px;
            }

            /* CHAT AREA */
            .chat-area {
                flex: 1;
                display: flex;
                flex-direction: column;
                background: var(--bg-chat);
                position: relative;
                overflow: hidden;
            }
            .chat-placeholder {
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                color: var(--text-muted);
                text-align: center;
            }
            .chat-placeholder h3 { font-size: 1.4rem; color: var(--text-main); margin-bottom: 8px; }

            /* ACTIVE CHAT UI */
            #active-chat { display: none; flex-direction: column; flex: 1; overflow: hidden; }
            .top-bar {
                background: var(--bg-navbar);
                border-bottom: 1px solid var(--border);
                padding: 16px 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                z-index: 5;
            }
            .top-bar h2 { font-size: 1.1rem; font-weight: 700; color: var(--text-main); }
            
            .btn-clear-chat {
                padding: 6px 12px;
                background: transparent;
                color: var(--text-muted);
                border: 1px solid var(--border);
                border-radius: 6px;
                font-size: 0.78rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            .btn-clear-chat:hover { background: #fef2f2; color: #ef4444; border-color: #fca5a5; }

            #messages-container {
                flex: 1;
                padding: 24px 40px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            #messages-container::-webkit-scrollbar { width: 6px; }
            #messages-container::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }

            /* MESSAGES */
            .msg-wrapper { display: flex; flex-direction: column; max-width: 65%; }
            .msg-wrapper.me { align-self: flex-end; align-items: flex-end; }
            .msg-wrapper.other { align-self: flex-start; align-items: flex-start; }
            .msg-bubble {
                padding: 10px 16px;
                border-radius: 12px;
                font-size: 0.95rem;
                line-height: 1.5;
                word-wrap: break-word;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            }
            .msg-wrapper.other .msg-bubble { background: var(--white); color: var(--text-main); border-top-left-radius: 0px; }
            .msg-wrapper.me .msg-bubble { background: var(--primary); color: var(--white); border-top-right-radius: 0px; }
            .msg-author { font-size: 0.75rem; font-weight: 600; margin-bottom: 4px; opacity: 0.8; }
            .msg-author.clickable { cursor: pointer; transition: opacity 0.2s; }
            .msg-author.clickable:hover { text-decoration: underline; opacity: 1; }
            .msg-wrapper.me .msg-author { display: none; }
            .msg-footer { display: flex; align-items: center; justify-content: flex-end; gap: 6px; margin-top: 4px; font-size: 0.68rem; opacity: 0.7; }
            .sys-msg-wrapper { align-self: center; margin: 12px 0; }
            .sys-bubble { background: #e2e8f0; color: var(--text-muted); padding: 4px 14px; border-radius: 16px; font-size: 0.75rem; font-weight: 500; }

            /* INPUT AREA */
            .bottom-bar { background: var(--bg-chat); padding: 16px 40px 24px 40px; display: flex; justify-content: center; }
            .input-wrapper { display: flex; align-items: center; background: var(--white); border-radius: 24px; padding: 8px 12px 8px 24px; width: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid var(--border); }
            .input-wrapper input { flex: 1; border: none; background: transparent; padding: 0; margin-right: 12px; }
            .input-wrapper input:focus { border: none; box-shadow: none; }
            .btn-send { padding: 10px 24px; background: var(--primary); color: white; border: none; border-radius: 20px; font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: background 0.2s; display: flex; align-items: center; gap: 6px; }
            .btn-send:hover { background: var(--primary-hover); }

            /* --- MODALS --- */
            .modal-overlay {
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.4);
                display: flex; align-items: center; justify-content: center;
                z-index: 1000;
            }
            .modal-box {
                width: 100%;
                max-width: 400px;
                background: var(--white);
                border-radius: 16px;
                padding: 32px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                position: relative;
            }
            .modal-close {
                position: absolute; top: 16px; right: 20px;
                font-size: 1.5rem; cursor: pointer; color: var(--text-muted);
            }
            .modal-close:hover { color: var(--text-main); }
            .modal-box h2 { font-size: 1.3rem; margin-bottom: 20px; color: var(--text-main); }
            
            /* Members List specifically */
            .member-item {
                display: flex; align-items: center; padding: 12px; border-radius: 8px; cursor: pointer; transition: background 0.2s;
            }
            .member-item:hover { background: var(--hover-bg); }
            .member-item strong { font-size: 0.95rem; color: var(--primary); }

        </style>
    </head>
    <body>
        
        <!-- GLOBAL AUTH SECTION -->
        <div id="global-auth-section">
            <div class="auth-box">
                <h1>sechat</h1>
                <p>Sign in to start messaging</p>
                <div class="tabs">
                    <div id="tab-signin" class="tab active" onclick="switchGlobalTab('signin')">Sign In</div>
                    <div id="tab-signup" class="tab" onclick="switchGlobalTab('signup')">Sign Up</div>
                </div>
                <form id="signin-form" onsubmit="handleSignIn(event)">
                    <div class="input-group">
                        <label>Username</label>
                        <input type="text" id="globalUsernameInput" placeholder="Enter username..." required />
                    </div>
                    <div class="input-group">
                        <label>Password</label>
                        <input type="password" id="globalPasswordInput" placeholder="••••••••" required />
                    </div>
                    <button type="submit" class="btn-submit">Log In</button>
                    <div id="signinStatus" class="status"></div>
                </form>
                <form id="signup-form" onsubmit="handleSignUp(event)" style="display: none;">
                    <div class="input-group">
                        <label>Choose Username</label>
                        <input type="text" id="signupUsernameInput" placeholder="Enter username..." required />
                    </div>
                    <div class="input-group">
                        <label>Choose Password</label>
                        <input type="password" id="signupPasswordInput" placeholder="••••••••" required />
                    </div>
                    <button type="submit" class="btn-submit">Sign Up</button>
                    <div id="signupStatus" class="status"></div>
                </form>
            </div>
        </div>

        <!-- TOP NAVBAR -->
        <nav class="navbar" id="top-navbar">
            <div class="nav-left">sechat</div>
            <div class="nav-right">
                <span>Logged in as <strong id="nav-username"></strong></span>
                <button class="btn-outline" onclick="openModal('join')">Join Room</button>
                <button class="btn-outline" onclick="openModal('create')">Create Room</button>
                <button class="btn-outline btn-logout" onclick="handleLogout()">Sign Out</button>
            </div>
        </nav>

        <!-- APP SPLIT PANE -->
        <div id="app-container">
            <!-- SIDEBAR -->
            <div class="sidebar">
                <div class="sidebar-header">
                    <h2>Chats</h2>
                </div>
                <div class="sidebar-content" id="sidebar-chats-list">
                    <!-- Chat items dynamically injected here -->
                </div>
            </div>

            <!-- MAIN CHAT AREA -->
            <div class="chat-area">
                <div id="chat-placeholder" class="chat-placeholder">
                    <h3>Welcome to sechat</h3>
                    <p>Select a room from the sidebar to start messaging.</p>
                </div>

                <div id="active-chat">
                    <div class="top-bar">
                        <h2 id="ws-group">Group Name</h2>
                        <div style="display: flex; gap: 10px;">
                            <button class="btn-outline" onclick="showMembers()">👥 Members</button>
                            <button class="btn-outline" onclick="leaveChat(null, currentGroupId)">Leave Room</button>
                            <button class="btn-clear-chat" onclick="clearChat()">Remove Chat History</button>
                        </div>
                    </div>

                    <div id="messages-container"></div>

                    <form class="bottom-bar" onsubmit="sendMessage(event)">
                        <div class="input-wrapper">
                            <input type="text" id="messageText" placeholder="Type a message..." autocomplete="off" required />
                            <button type="submit" class="btn-send">
                                <span>Send</span>
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <!-- MODALS -->
        <div id="modal-overlay" class="modal-overlay" style="display: none;">
            <!-- JOIN MODAL -->
            <div id="modal-join" class="modal-box" style="display: none;">
                <span class="modal-close" onclick="closeModals()">&times;</span>
                <h2>Join a Room</h2>
                <form id="join-form" onsubmit="handleJoinModal(event)">
                    <div class="input-group">
                        <label for="joinGroupId">Group Code</label>
                        <input type="text" id="joinGroupId" placeholder="Enter group code..." required />
                    </div>
                    <div class="input-group">
                        <label for="joinPassword">Group Password</label>
                        <input type="password" id="joinPassword" placeholder="••••••••" required />
                    </div>
                    <button type="submit" class="btn-submit">Enter Room</button>
                    <div id="joinStatus" class="status"></div>
                </form>
            </div>
            
            <!-- CREATE MODAL -->
            <div id="modal-create" class="modal-box" style="display: none;">
                <span class="modal-close" onclick="closeModals()">&times;</span>
                <h2>Create a Room</h2>
                <form id="create-form" onsubmit="handleCreateModal(event)">
                    <div class="input-group">
                        <label for="createGroupName">Group Title</label>
                        <input type="text" id="createGroupName" placeholder="e.g. Gamers" required />
                    </div>
                    <div class="input-group">
                        <label for="createGroupId">Unique Group Code</label>
                        <input type="text" id="createGroupId" placeholder="e.g. room123" required />
                    </div>
                    <div class="input-group">
                        <label for="createPassword">Set Room Password</label>
                        <input type="password" id="createPassword" placeholder="••••••••" required />
                    </div>
                    <button type="submit" class="btn-submit">Create Room</button>
                    <div id="createStatus" class="status"></div>
                </form>
            </div>

            <!-- MEMBERS MODAL -->
            <div id="modal-members" class="modal-box" style="display: none;">
                <span class="modal-close" onclick="closeModals()">&times;</span>
                <h2>Room Members</h2>
                <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 12px; margin-top: -12px;">Click a username to send a Direct Message</p>
                <div id="members-list" style="display: flex; flex-direction: column; max-height: 300px; overflow-y: auto;">
                    <!-- Members injected here -->
                </div>
            </div>
        </div>

        <script>
            // Globals
            var currentGroupId = "";
            var globalAuthUsername = "";
            let currentCryptoKey = null;
            let savedChats = [];
            
            // Multi-socket state
            let activeSockets = {}; // group_id -> WebSocket
            let chatHistories = {}; // group_id -> Array of messages
            let unreadCounts = {};  // group_id -> Int

            function loadUserChats() {
                if (!globalAuthUsername) {
                    savedChats = [];
                    return;
                }
                try {
                    const raw = localStorage.getItem(`saved_chats_${globalAuthUsername}`);
                    savedChats = raw ? JSON.parse(raw) : [];
                } catch (e) {
                    savedChats = [];
                }
            }

            function persistUserChats() {
                if (!globalAuthUsername) return;
                localStorage.setItem(`saved_chats_${globalAuthUsername}`, JSON.stringify(savedChats));
            }

            function arrayBufferToBase64(buffer) {
                let binary = '';
                const bytes = new Uint8Array(buffer);
                for (let i = 0; i < bytes.byteLength; i++) { binary += String.fromCharCode(bytes[i]); }
                return window.btoa(binary);
            }
            function base64ToArrayBuffer(base64) {
                const binary = window.atob(base64);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) { bytes[i] = binary.charCodeAt(i); }
                return bytes.buffer;
            }
            async function deriveKey(groupId, password) {
                const enc = new TextEncoder();
                const keyMaterial = await crypto.subtle.importKey(
                    "raw", enc.encode(password), { name: "PBKDF2" }, false, ["deriveBits", "deriveKey"]
                );
                return crypto.subtle.deriveKey(
                    { name: "PBKDF2", salt: enc.encode(groupId), iterations: 100000, hash: "SHA-256" },
                    keyMaterial, { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]
                );
            }
            async function encryptText(text, key) {
                const enc = new TextEncoder();
                const iv = crypto.getRandomValues(new Uint8Array(12));
                const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, key, enc.encode(text));
                return JSON.stringify({ iv: arrayBufferToBase64(iv), ciphertext: arrayBufferToBase64(ciphertext) });
            }
            async function decryptText(jsonStr, key) {
                try {
                    const data = JSON.parse(jsonStr);
                    if (!data.iv || !data.ciphertext) return jsonStr;
                    const decryptedBuffer = await crypto.subtle.decrypt(
                        { name: "AES-GCM", iv: base64ToArrayBuffer(data.iv) }, key, base64ToArrayBuffer(data.ciphertext)
                    );
                    return new TextDecoder().decode(decryptedBuffer);
                } catch (e) {
                    return "<Encrypted/Invalid Message>";
                }
            }

            window.addEventListener('DOMContentLoaded', () => {
                // Clear any legacy un-scoped saved_chats
                localStorage.removeItem('saved_chats');
                const savedUsername = localStorage.getItem('global_auth_username');
                if (savedUsername) {
                    document.getElementById('globalUsernameInput').value = savedUsername;
                }
            });

            function switchGlobalTab(tab) {
                if (tab === 'signin') {
                    document.getElementById('tab-signin').classList.add('active');
                    document.getElementById('tab-signup').classList.remove('active');
                    document.getElementById('signin-form').style.display = 'block';
                    document.getElementById('signup-form').style.display = 'none';
                } else {
                    document.getElementById('tab-signup').classList.add('active');
                    document.getElementById('tab-signin').classList.remove('active');
                    document.getElementById('signup-form').style.display = 'block';
                    document.getElementById('signin-form').style.display = 'none';
                }
            }

            async function handleSignUp(event) {
                event.preventDefault();
                const username = document.getElementById("signupUsernameInput").value.trim();
                const password = document.getElementById("signupPasswordInput").value.trim();
                const statusEl = document.getElementById("signupStatus");
                try {
                    const res = await fetch('/signup', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password })
                    });
                    const data = await res.json();
                    if (data.success) {
                        statusEl.style.color = "#34d399";
                        statusEl.textContent = data.message;
                        document.getElementById("globalUsernameInput").value = username;
                        document.getElementById("globalPasswordInput").value = password;
                        setTimeout(() => switchGlobalTab('signin'), 1000);
                    } else {
                        statusEl.style.color = "#f87171";
                        statusEl.textContent = data.message;
                    }
                } catch (err) { statusEl.style.color = "#f87171"; statusEl.textContent = "Error signing up."; }
            }

            async function handleSignIn(event) {
                event.preventDefault();
                const username = document.getElementById("globalUsernameInput").value.trim();
                const password = document.getElementById("globalPasswordInput").value.trim();
                const statusEl = document.getElementById("signinStatus");
                try {
                    const res = await fetch('/signin', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password })
                    });
                    const data = await res.json();
                    if (data.success) {
                        // Close any existing sockets before switching user
                        for (const gid in activeSockets) {
                            try { activeSockets[gid].close(); } catch(e) {}
                        }
                        activeSockets = {};
                        chatHistories = {};
                        unreadCounts = {};
                        currentGroupId = "";
                        currentCryptoKey = null;

                        // Legacy cleanup
                        localStorage.removeItem('saved_chats');

                        localStorage.setItem('global_auth_username', username);
                        globalAuthUsername = username;

                        // Load chats exclusively saved for this user
                        loadUserChats();

                        document.getElementById("global-auth-section").style.display = "none";
                        document.getElementById("top-navbar").style.display = "flex";
                        document.getElementById("app-container").style.display = "flex";
                        document.getElementById("nav-username").textContent = username;
                        document.getElementById("chat-placeholder").style.display = "flex";
                        document.getElementById("active-chat").style.display = "none";
                        
                        // Boot up all sockets in the background for this user's joined rooms only!
                        for (const chat of savedChats) {
                            connectSocket(chat.group_id, chat.password);
                        }
                        renderSidebar();
                    } else {
                        statusEl.style.color = "#f87171";
                        statusEl.textContent = data.message;
                    }
                } catch (err) { statusEl.style.color = "#f87171"; statusEl.textContent = "Error signing in."; }
            }

            function handleLogout() {
                for (const gid in activeSockets) {
                    try { activeSockets[gid].close(); } catch(e) {}
                }
                activeSockets = {};
                chatHistories = {};
                unreadCounts = {};
                savedChats = [];
                currentGroupId = "";
                globalAuthUsername = "";
                currentCryptoKey = null;

                localStorage.removeItem('global_auth_username');

                document.getElementById("top-navbar").style.display = "none";
                document.getElementById("app-container").style.display = "none";
                document.getElementById("active-chat").style.display = "none";
                document.getElementById("chat-placeholder").style.display = "flex";
                document.getElementById("messages-container").innerHTML = "";
                document.getElementById("global-auth-section").style.display = "flex";
                document.getElementById("globalPasswordInput").value = "";
                document.getElementById("signinStatus").textContent = "";
                document.getElementById("signupStatus").textContent = "";
            }

            // --- MODAL LOGIC ---
            function openModal(type) {
                document.getElementById('modal-overlay').style.display = 'flex';
                document.getElementById('modal-join').style.display = type === 'join' ? 'block' : 'none';
                document.getElementById('modal-create').style.display = type === 'create' ? 'block' : 'none';
                document.getElementById('modal-members').style.display = type === 'members' ? 'block' : 'none';
                document.getElementById('joinStatus').textContent = '';
                document.getElementById('createStatus').textContent = '';
            }
            function closeModals() {
                document.getElementById('modal-overlay').style.display = 'none';
                document.getElementById('modal-join').style.display = 'none';
                document.getElementById('modal-create').style.display = 'none';
                document.getElementById('modal-members').style.display = 'none';
            }

            async function handleCreateModal(event) {
                event.preventDefault();
                const group_name = document.getElementById("createGroupName").value.trim();
                const group_id = document.getElementById("createGroupId").value.trim();
                const password = document.getElementById("createPassword").value.trim();
                const statusEl = document.getElementById("createStatus");
                try {
                    const res = await fetch('/create_group', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ group_id, group_name, password })
                    });
                    const data = await res.json();
                    if (data.success) {
                        statusEl.style.color = "#34d399";
                        statusEl.textContent = "Group created! Joining...";
                        saveAndConnect(group_id, password, group_name);
                    } else {
                        statusEl.style.color = "#f87171";
                        statusEl.textContent = data.message;
                    }
                } catch (err) { statusEl.style.color = "#f87171"; statusEl.textContent = "Error creating group."; }
            }

            async function handleJoinModal(event) {
                event.preventDefault();
                const group_id = document.getElementById("joinGroupId").value.trim();
                const password = document.getElementById("joinPassword").value.trim();
                const statusEl = document.getElementById("joinStatus");
                
                statusEl.style.color = "#64748b";
                statusEl.textContent = "Connecting...";

                const success = await connectSocket(group_id, password);
                if (success) {
                    saveChat(group_id, password, group_id);
                    switchToChat(group_id);
                    closeModals();
                } else {
                    statusEl.style.color = "#f87171";
                    statusEl.textContent = "Invalid Group Code or Password!";
                }
            }

            function saveChat(group_id, password, title) {
                if (!globalAuthUsername) return;
                const existingIndex = savedChats.findIndex(c => c.group_id === group_id);
                if (existingIndex >= 0) {
                    savedChats[existingIndex].password = password;
                    if (title) savedChats[existingIndex].title = title;
                } else {
                    savedChats.push({ group_id, password, title: title || group_id });
                }
                persistUserChats();
                renderSidebar();
            }

            function leaveChat(event, group_id) {
                if (event) event.stopPropagation();
                if (!group_id) return;
                if (!confirm(`Are you sure you want to leave this room?`)) return;
                if (activeSockets[group_id]) {
                    try { activeSockets[group_id].close(); } catch(e) {}
                    delete activeSockets[group_id];
                }
                delete chatHistories[group_id];
                delete unreadCounts[group_id];
                savedChats = savedChats.filter(c => c.group_id !== group_id);
                persistUserChats();
                if (currentGroupId === group_id) {
                    currentGroupId = "";
                    currentCryptoKey = null;
                    document.getElementById("active-chat").style.display = "none";
                    document.getElementById("chat-placeholder").style.display = "flex";
                }
                renderSidebar();
            }

            async function saveAndConnect(group_id, password, title) {
                const success = await connectSocket(group_id, password);
                if (success) {
                    saveChat(group_id, password, title);
                    switchToChat(group_id);
                    closeModals();
                }
            }

            function renderSidebar() {
                const list = document.getElementById('sidebar-chats-list');
                list.innerHTML = '';
                if (savedChats.length === 0) {
                    list.innerHTML = `<div style="padding: 20px; color: var(--text-muted); font-size: 0.9rem; text-align: center;">No chats yet. Create or Join one!</div>`;
                    return;
                }
                
                savedChats.forEach(chat => {
                    const item = document.createElement('div');
                    item.className = `chat-item ${chat.group_id === currentGroupId ? 'active' : ''}`;
                    item.onclick = () => switchToChat(chat.group_id);
                    
                    const isDM = chat.group_id.startsWith("dm_");
                    const avatarLetter = isDM ? '👤' : (chat.title || chat.group_id).charAt(0).toUpperCase();
                    
                    const unreadCount = unreadCounts[chat.group_id] || 0;
                    const badgeHtml = unreadCount > 0 ? `<div class="unread-badge">${unreadCount}</div>` : '';

                    item.innerHTML = `
                        <div class="chat-avatar">${avatarLetter}</div>
                        <div class="chat-info">
                            <div class="chat-title-group">
                                <h4>${escapeHTML(chat.title || chat.group_id)}</h4>
                                <p>${escapeHTML(chat.group_id)}</p>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                ${badgeHtml}
                                <button class="btn-leave-chat" title="Leave room" onclick="leaveChat(event, '${escapeHTML(chat.group_id)}')">&times;</button>
                            </div>
                        </div>
                    `;
                    list.appendChild(item);
                });
            }

            // Initializes the socket connection in the background
            async function connectSocket(group_id, password) {
                if (activeSockets[group_id]) return true; // already connected
                try {
                    const res = await fetch('/verify_group', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ group_id, password })
                    });
                    const data = await res.json();
                    if (!data.success) return false;
                    
                    if (!chatHistories[group_id]) chatHistories[group_id] = [];
                    
                    const ws = new WebSocket(`ws://${location.host}/ws/${group_id}/${globalAuthUsername}?token=${data.token}`);
                    activeSockets[group_id] = ws;

                    ws.onmessage = async function(event) {
                        if (event.data === "__SYS_CLEAR_CHAT__") {
                            chatHistories[group_id] = [];
                            if (currentGroupId === group_id) document.getElementById('messages-container').innerHTML = '';
                            return;
                        }
                        
                        let isSys = false;
                        let text = event.data;
                        if (typeof event.data === 'string' && event.data.startsWith("@SYS:JOIN:")) {
                            const joinedUser = event.data.substring(10);
                            text = `${joinedUser} joined the group`;
                            isSys = true;
                        }

                        // Save to memory
                        chatHistories[group_id].push({ type: isSys ? 'sys' : 'msg', rawText: text, isMe: false });
                        
                        if (currentGroupId === group_id) {
                            if (isSys) appendSystemMessage(text);
                            else await appendMessage(text, false);
                        } else {
                            // Increment unread badge!
                            unreadCounts[group_id] = (unreadCounts[group_id] || 0) + 1;
                            renderSidebar();
                        }
                    };
                    
                    ws.onclose = () => { delete activeSockets[group_id]; };
                    return true;
                } catch (err) { 
                    console.error(err);
                    return false; 
                }
            }

            // Switches the active UI view to a specific chat
            async function switchToChat(group_id) {
                const chat = savedChats.find(c => c.group_id === group_id);
                if (!chat) return;
                
                currentGroupId = group_id;
                unreadCounts[group_id] = 0; // clear unread badge
                renderSidebar();
                
                document.getElementById("chat-placeholder").style.display = "none";
                document.getElementById("active-chat").style.display = "flex";
                document.getElementById("ws-group").textContent = chat.title || group_id;
                
                currentCryptoKey = await deriveKey(group_id, chat.password);
                
                const container = document.getElementById('messages-container');
                container.innerHTML = '';
                
                // Render history from memory
                const history = chatHistories[group_id] || [];
                for (const msg of history) {
                    if (msg.type === 'sys') {
                        appendSystemMessage(msg.rawText);
                    } else {
                        await appendMessage(msg.rawText, msg.isMe);
                    }
                }
            }

            // --- MEMBERS & DMs LOGIC ---
            async function showMembers() {
                if (!currentGroupId) return;
                try {
                    const res = await fetch(`/group_members/${currentGroupId}`);
                    const data = await res.json();
                    const list = document.getElementById('members-list');
                    list.innerHTML = '';
                    if (!data.members || data.members.length === 0) {
                        list.innerHTML = `<p style="color: var(--text-muted); text-align: center;">No active members found.</p>`;
                    } else {
                        data.members.forEach(member => {
                            const isMe = member === globalAuthUsername;
                            const div = document.createElement('div');
                            div.className = 'member-item';
                            div.innerHTML = `<strong>${escapeHTML(member)}</strong> ${isMe ? '<span style="color: #94a3b8; font-size: 0.8rem; margin-left: 8px;">(You)</span>' : ''}`;
                            if (!isMe) {
                                div.onclick = () => {
                                    closeModals();
                                    startDM(member);
                                };
                            }
                            list.appendChild(div);
                        });
                    }
                    openModal('members');
                } catch(e) { console.error(e); }
            }

            async function startDM(targetUser) {
                if(targetUser === globalAuthUsername) return; // Cannot DM yourself
                try {
                    const res = await fetch('/initiate_dm', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user1: globalAuthUsername, user2: targetUser })
                    });
                    const data = await res.json();
                    if (data.success) {
                        saveAndConnect(data.group_id, data.password, data.group_name);
                    } else {
                        alert("Error starting DM: " + data.message);
                    }
                } catch(e) { console.error(e); }
            }

            async function clearChat() {
                if (!currentGroupId) return;
                if (!confirm("Are you sure you want to remove all chat history for this group?")) return;
                try {
                    const res = await fetch('/clear_chat', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ group_id: currentGroupId })
                    });
                    const data = await res.json();
                    if (data.success) {
                        document.getElementById('messages-container').innerHTML = '';
                    } else { alert("Error clearing chat."); }
                } catch (err) { alert("Error clearing chat."); }
            }

            async function sendMessage(event) {
                event.preventDefault();
                if (!currentGroupId) return;
                const ws = activeSockets[currentGroupId];
                if (!ws) return;
                
                var input = document.getElementById("messageText");
                var text = input.value.trim();
                if (!text) return;

                const encryptedJson = await encryptText(text, currentCryptoKey);
                ws.send(encryptedJson);
                
                const rawText = `${globalAuthUsername}:${encryptedJson}`;
                if (!chatHistories[currentGroupId]) chatHistories[currentGroupId] = [];
                chatHistories[currentGroupId].push({ type: 'msg', rawText: rawText, isMe: true });
                
                await appendMessage(rawText, true);
                input.value = '';
            }

            const USER_COLORS = ['#ec4899', '#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444'];
            function getUsernameColor(name) {
                let hash = 0;
                for (let i = 0; i < name.length; i++) { hash = name.charCodeAt(i) + ((hash << 5) - hash); }
                return USER_COLORS[Math.abs(hash) % USER_COLORS.length];
            }

            function formatTime() {
                const now = new Date();
                let hours = now.getHours();
                let minutes = now.getMinutes();
                hours = hours % 12 || 12;
                minutes = minutes < 10 ? '0' + minutes : minutes;
                return `${hours}:${minutes}`;
            }

            function escapeHTML(str) {
                return str.replace(/[&<>'"]/g, tag => ({
                    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
                }[tag]));
            }

            function appendSystemMessage(text) {
                var container = document.getElementById('messages-container');
                var wrapper = document.createElement('div');
                wrapper.className = 'sys-msg-wrapper';
                wrapper.innerHTML = `<div class="sys-bubble"><span>${escapeHTML(text)}</span></div>`;
                container.appendChild(wrapper);
                container.scrollTop = container.scrollHeight;
            }

            async function appendMessage(rawText, isMe) {
                var container = document.getElementById('messages-container');
                var wrapper = document.createElement('div');
                
                const parts = rawText.split(/:(.*)/);
                let sender = "User";
                let textContent = rawText;
                if (parts.length >= 2) {
                    sender = parts[0].trim();
                    textContent = parts[1].trim();
                }

                if (currentCryptoKey) { textContent = await decryptText(textContent, currentCryptoKey); }
                textContent = escapeHTML(textContent);
                sender = escapeHTML(sender);

                wrapper.className = `msg-wrapper ${isMe ? 'me' : 'other'}`;
                
                const userColor = isMe ? '' : `color: ${getUsernameColor(sender)};`;
                const clickAction = isMe ? '' : `onclick="startDM('${sender}')"`;
                const clickClass = isMe ? '' : 'clickable';

                wrapper.innerHTML = `
                    <div class="msg-bubble">
                        <div class="msg-author ${clickClass}" style="${userColor}" ${clickAction}>${sender}</div>
                        <span>${textContent}</span>
                        <div class="msg-footer"><span>${formatTime()}</span></div>
                    </div>
                `;
                container.appendChild(wrapper);
                container.scrollTop = container.scrollHeight;
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.post("/signup")
async def signup(request: Request):
    data = await request.json()
    try:
        await create_user(data["username"], data["password"])
        return {"success": True, "message": "Account created! You can now sign in."}
    except Exception:
        return {"success": False, "message": "Username already exists."}

@app.post("/signin")
async def signin(request: Request):
    data = await request.json()
    is_valid = await verify_user(data["username"], data["password"])
    if is_valid:
        return {"success": True}
    else:
        return {"success": False, "message": "Invalid Username or Password!"}

@app.post("/create_group")
async def create(request: Request):
    data = await request.json()
    try:
        await create_group(data["group_id"], data["group_name"], data["password"])
        return {"success": True, "message": "Group created! Switching to Join..."}
    except Exception as e:
        return {"success": False, "message": "Group Code already exists or database error."}

@app.post("/verify_group")
async def verify(request: Request):
    data = await request.json()
    is_valid = await verify_group(data["group_id"], data["password"])
    if is_valid:
        token = secrets.token_urlsafe(16)
        active_tokens[token] = data["group_id"]
        return {"success": True, "token": token}
    else:
        return {"success": False, "message": "Invalid Group Code or Password!"}

@app.get("/group_members/{group_id}")
async def group_members(group_id: str):
    members = manager.get_members(group_id)
    return {"members": members}

@app.post("/initiate_dm")
async def initiate_dm(request: Request):
    data = await request.json()
    u1 = data["user1"]
    u2 = data["user2"]
    
    users = sorted([u1, u2])
    dm_group_id = f"dm_{users[0]}_{users[1]}"
    
    dm_group_name = f"DM: {users[0]} & {users[1]}"
    password = get_dm_password(u1, u2)
    
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT group_id FROM groups WHERE group_id = ?", (dm_group_id,))
        row = await cursor.fetchone()
        
    if row is None:
        try:
            await create_group(dm_group_id, dm_group_name, password)
        except Exception:
            pass 
            
    return {"success": True, "group_id": dm_group_id, "group_name": dm_group_name, "password": password}

@app.post("/clear_chat")
async def clear_chat(request: Request):
    data = await request.json()
    group_id = data.get("group_id")
    if group_id:
        await clear_group_messages(group_id)
        await manager.broadcast("__SYS_CLEAR_CHAT__", group_id)
        return {"success": True, "message": "Chat history wiped from database!"}
    return {"success": False, "message": "Group ID required."}

@app.websocket("/ws/{group_id}/{username}")
async def websocket_endpoint(websocket: WebSocket, group_id: str, username: str, token: str = None):
    if not token or active_tokens.get(token) != group_id:
        await websocket.close(code=1008)
        return
    del active_tokens[token]

    await manager.connect(websocket, group_id, username)
    await manager.broadcast(f"@SYS:JOIN:{username}", group_id)

    try:
        history = await get_group_history(group_id, limit=50)
        for msg in history:
            await manager.send_personal_message(f"{msg['username']}: {msg['content']}", websocket)

        while True:
            data = await websocket.receive_text()
            await save_message(group_id, username, data)
            await manager.broadcast(f"{username}: {data}", group_id, sender=websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, group_id)
