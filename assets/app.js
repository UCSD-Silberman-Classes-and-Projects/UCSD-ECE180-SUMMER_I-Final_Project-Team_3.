// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

let currentAudio = null;
let audioType = null;
let audioInput;
let errorContainer;

// Tracks mute state as reported by the physical buttons, so it can be
// applied to stem cards even if they're created after a button was pressed.
let muteState = { vocal: false, drums: false, bass: false, other: false };

initializeElements();

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);

ui.on_message('separation_result', data => {
  console.log('📥 Received separation_result:', data);
  handleSeparationResult(data);
});

ui.on_message('separation_error', data => {
  console.log('📥 Received separation_error:', data);
  showError(`Separation failed: ${data.error}`);
  setButtonState('ready');
});

ui.on_message('stem_mute_update', data => {
  console.log('📥 Received stem_mute_update:', data);
  muteState[data.stem] = data.muted;
  updateStemChip(data.stem, data.muted);
  updateStemCardMuteState(data.stem, data.muted);
});

ui.on_message('final_mix_result', data => {
  console.log('📥 Received final_mix_result:', data);
  handleFinalMixResult(data);
});

ui.on_message('final_mix_error', data => {
  console.log('📥 Received final_mix_error:', data);
  showFinalMixError(data.error);
});

function onAudioPreviewClick() {
  if (!currentAudio) {
    audioInput.click();
  }
}

function onUIConnected() {
  if (errorContainer) {
    errorContainer.style.display = 'none';
    errorContainer.textContent = '';
  }
}

function onUIDisconnected() {
  if (errorContainer) {
    errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
    errorContainer.style.display = 'block';
  }
}

function initializeElements() {
  audioInput = document.getElementById('audioInput');
  const audioPreview = document.getElementById('audioPreview');
  const separateButton = document.getElementById('separateButton');
  const uploadNewButton = document.getElementById('uploadNewButton');
  errorContainer = document.getElementById('error-container');

  audioInput.addEventListener('change', handleAudioUpload);
  audioPreview.addEventListener('click', onAudioPreviewClick);

  audioPreview.addEventListener('dragover', e => {
    e.preventDefault();
    audioPreview.classList.add('drag-over');
  });

  audioPreview.addEventListener('dragleave', () => {
    audioPreview.classList.remove('drag-over');
  });

  audioPreview.addEventListener('drop', e => {
    e.preventDefault();
    audioPreview.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0 && isAudioFile(files[0])) {
      handleAudioFile(files[0]);
    }
  });

  separateButton.addEventListener('click', runSeparation);
  uploadNewButton.addEventListener('click', uploadNewSong);
}

function isAudioFile(file) {
  return file.type.startsWith('audio/') || /\.(wav|mp3)$/i.test(file.name);
}

function uploadNewSong() {
  currentAudio = null;
  const audioPreview = document.getElementById('audioPreview');
  const resultsContainer = document.getElementById('resultsContainer');

  audioPreview.innerHTML = `
        <div class="upload-placeholder">
            <p class="drag-and-drop">Drag & drop a song here, or</p>
            <button class="drag-and-drop-button">Upload</button>
            <div>
            <span class="drag-and-drop-text border">File WAV or MP3</span><span class="drag-and-drop-text">Max 20MB</span>
            </div>
            <input type="file" id="audioInput" accept=".wav,.mp3,audio/*" style="display: none">
        </div>
    `;
  audioPreview.style.border = '1px dashed #7F8C8D';
  resultsContainer.innerHTML = '';
  resetFinalMixSection();

  audioInput = document.getElementById('audioInput');
  audioInput.addEventListener('change', handleAudioUpload);

  setButtonState('initial');
  clearStatus();
}

function handleAudioUpload(event) {
  const file = event.target.files[0];
  if (file) {
    handleAudioFile(file);
  }
}

function handleAudioFile(file) {
  if (!isAudioFile(file)) {
    showError('Please select a valid WAV or MP3 file');
    return;
  }

  const reader = new FileReader();
  reader.onload = e => {
    currentAudio = e.target.result.split(',')[1];
    audioType = file.type || (file.name.toLowerCase().endsWith('.mp3') ? 'audio/mpeg' : 'audio/wav');

    const audioPreview = document.getElementById('audioPreview');
    audioPreview.innerHTML = `
      <div class="file-selected">
        <p class="file-name">${file.name}</p>
        <audio controls src="${e.target.result}" class="preview-audio"></audio>
      </div>
    `;
    audioPreview.style.border = 'none';

    setButtonState('ready');
    clearStatus();
    resetFinalMixSection();
  };
  reader.readAsDataURL(file);
}

function runSeparation() {
  if (!currentAudio) {
    showError('No song available for separation');
    return;
  }

  setButtonState('separating');
  showStatus('Separating stems... this may take a while.', 'info');
  resetFinalMixSection();

  ui.send_message('separate_song', {
    audio: currentAudio,
    audio_type: audioType,
  });
}

function handleSeparationResult(data) {
  if (data.error || !data.success) {
    showError(`Separation failed: ${data.error || 'Unknown error'}`);
    setButtonState('ready');
    return;
  }

  const resultsContainer = document.getElementById('resultsContainer');
  resultsContainer.innerHTML = '';

  if (data.stems && Object.keys(data.stems).length > 0) {
    Object.entries(data.stems).forEach(([stemName, stemData]) => {
      const isMuted = stemData.muted ?? muteState[stemName] ?? false;
      muteState[stemName] = isMuted;

      const stemDiv = document.createElement('div');
      stemDiv.className = 'stem-card' + (isMuted ? ' muted' : '');
      stemDiv.id = `stem-card-${stemName}`;
      stemDiv.innerHTML = `
        <h3 class="stem-name">${stemName}</h3>
        <audio controls src="data:audio/wav;base64,${stemData.audio_base64}" ${isMuted ? 'muted' : ''}></audio>
        <a class="stem-download" download="${stemName}.wav" href="data:audio/wav;base64,${stemData.audio_base64}">Download</a>
        <span class="stem-status-badge">${isMuted ? 'Muted' : 'Active'}</span>
      `;
      resultsContainer.appendChild(stemDiv);
    });

    showStatus(`Separation completed in ${data.processing_time}!`, 'success');
    document.getElementById('finalMixHint').textContent =
      'Press the buttons on the board to mute/unmute stems, then press the Finalize button to lock in your mix.';
  } else {
    showStatus('No stems were returned.', 'info');
  }
  setButtonState('completed');
}

function handleFinalMixResult(data) {
  const resultBox = document.getElementById('finalMixResult');
  const hint = document.getElementById('finalMixHint');

  const removedList = data.removed_stems && data.removed_stems.length
    ? data.removed_stems.map(capitalize).join(', ')
    : 'None';
  const keptList = data.kept_stems && data.kept_stems.length
    ? data.kept_stems.map(capitalize).join(', ')
    : 'None';

  hint.textContent = '';

  resultBox.style.display = 'flex';
  resultBox.className = 'final-mix-result';
  resultBox.innerHTML = `
    <div class="final-mix-info">
      <p class="final-mix-row"><strong>Removed:</strong> ${removedList}</p>
      <p class="final-mix-row"><strong>Kept:</strong> ${keptList}</p>
      ${data.is_mock_audio ? '<p class="final-mix-note">Note: playback below is a placeholder until the real separation model is wired in. The removed/kept list above reflects your actual button presses.</p>' : ''}
    </div>
    <audio controls src="data:audio/wav;base64,${data.audio_base64}" class="final-mix-audio"></audio>
    <a class="stem-download" download="final_mix.wav" href="data:audio/wav;base64,${data.audio_base64}">Download Final Mix</a>
  `;
}

function showFinalMixError(message) {
  const resultBox = document.getElementById('finalMixResult');
  const hint = document.getElementById('finalMixHint');
  hint.textContent = '';
  resultBox.style.display = 'flex';
  resultBox.className = 'final-mix-result error';
  resultBox.innerHTML = `<p class="final-mix-row">${message}</p>`;
}

function resetFinalMixSection() {
  const resultBox = document.getElementById('finalMixResult');
  const hint = document.getElementById('finalMixHint');
  resultBox.style.display = 'none';
  resultBox.innerHTML = '';
  hint.textContent = 'Press the buttons on the board to mute/unmute stems, then press the Finalize button to lock in your mix.';
}

function capitalize(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

function updateStemChip(stem, muted) {
  const chip = document.getElementById(`chip-${stem}`);
  if (!chip) return;
  chip.classList.toggle('muted', muted);
  const statusEl = chip.querySelector('.stem-chip-status');
  if (statusEl) statusEl.textContent = muted ? 'Muted' : 'Active';
}

function updateStemCardMuteState(stem, muted) {
  const card = document.getElementById(`stem-card-${stem}`);
  if (!card) return;
  card.classList.toggle('muted', muted);

  const audioEl = card.querySelector('audio');
  if (audioEl) {
    audioEl.muted = muted;
    if (muted) audioEl.pause();
  }

  const badge = card.querySelector('.stem-status-badge');
  if (badge) badge.textContent = muted ? 'Muted' : 'Active';
}

function setButtonState(state) {
  const separateButton = document.getElementById('separateButton');
  const uploadNewButton = document.getElementById('uploadNewButton');

  switch (state) {
    case 'initial':
      separateButton.style.display = 'none';
      uploadNewButton.style.display = 'none';
      break;
    case 'ready':
      separateButton.style.display = 'inline-block';
      separateButton.disabled = false;
      separateButton.textContent = 'Separate Stems ▶';
      uploadNewButton.style.display = 'flex';
      break;
    case 'separating':
      separateButton.disabled = true;
      separateButton.textContent = 'Separating...';
      break;
    case 'completed':
      separateButton.style.display = 'inline-block';
      separateButton.disabled = false;
      separateButton.textContent = 'Run Again ▶';
      uploadNewButton.style.display = 'flex';
      break;
  }
}

function showStatus(message, type = 'info') {
  const statusElement = document.getElementById('statusMessage');
  statusElement.textContent = message;
  statusElement.className = `status-message ${type}`;
  statusElement.style.display = 'block';
}

function showError(message) {
  showStatus(message, 'error');
}

function clearStatus() {
  const statusElement = document.getElementById('statusMessage');
  statusElement.style.display = 'none';
  statusElement.textContent = '';
}