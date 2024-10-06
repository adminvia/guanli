from flask import Flask, render_template, request, redirect, url_for, jsonify
import subprocess
import re
import pty
import os
import select
import termios
import struct
import fcntl

app = Flask(__name__)

def run_screen_command(command):
    try:
        return subprocess.check_output(f"screen {command}", shell=True).decode('utf-8')
    except subprocess.CalledProcessError as e:
        return str(e)

def get_sessions():
    output = run_screen_command("-ls")
    sessions = []
    for line in output.split('\n')[1:-2]:
        match = re.search(r'\t(\d+\.\w+)\t', line)
        if match:
            session_id = match.group(1)
            session_name = line.split('\t')[-1]
            sessions.append({"id": session_id, "name": session_name})
    return sessions

@app.route('/')
def index():
    return render_template('index.html', sessions=get_sessions())

@app.route('/create', methods=['POST'])
def create():
    session_name = request.form['session_name']
    result = run_screen_command(f"-dmS {session_name}")
    return jsonify({"success": "Screen session created successfully" in result, "message": result})

@app.route('/kill', methods=['POST'])
def kill():
    session_id = request.form['session_id']
    result = run_screen_command(f"-X -S {session_id} quit")
    return jsonify({"success": "Screen session killed successfully" in result, "message": result})

@app.route('/rename', methods=['POST'])
def rename():
    session_id = request.form['session_id']
    new_name = request.form['new_name']
    result = run_screen_command(f"-S {session_id} sessionname {new_name}")
    return jsonify({"success": "Screen session renamed successfully" in result, "message": result})

@app.route('/sessions')
def sessions():
    return jsonify(get_sessions())

@app.route('/view/<session_id>')
def view_session(session_id):
    return render_template('view_session.html', session_id=session_id)

@app.route('/stream/<session_id>')
def stream(session_id):
    def generate():
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            ['screen', '-x', session_id],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid
        )

        while True:
            r, w, e = select.select([master_fd], [], [], 0.1)
            if master_fd in r:
                output = os.read(master_fd, 1024).decode('utf-8', errors='ignore')
                yield f"data: {output}\n\n"

            if process.poll() is not None:
                break

        os.close(master_fd)
        os.close(slave_fd)

    return app.response_class(generate(), mimetype='text/event-stream')

@app.route('/send_command/<session_id>', methods=['POST'])
def send_command(session_id):
    command = request.form['command']
    result = run_screen_command(f"-S {session_id} stuff '{command}\\n'")
    return jsonify({"success": True, "message": "Command sent successfully"})

if __name__ == '__main__':
    app.run(debug=True)