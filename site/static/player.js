/* 自定义播客播放器 + MediaSession (锁屏/AirPods/车机控件) */
(function () {
  const root = document.querySelector('[data-player]');
  if (!root) return;
  const audio = root.querySelector('audio');
  const btnPlay = root.querySelector('.btn-play');
  const iconPlay = root.querySelector('[data-icon-play]');
  const iconPause = root.querySelector('[data-icon-pause]');
  const btnBack = root.querySelector('[data-skip="-15"]');
  const btnFwd = root.querySelector('[data-skip="15"]');
  const bar = root.querySelector('.player-bar');
  const fill = root.querySelector('.player-bar-fill');
  const thumb = root.querySelector('.player-bar-thumb');
  const tNow = root.querySelector('.now');
  const tDur = root.querySelector('.dur');
  const speedBtns = root.querySelectorAll('.speed button');

  const fmt = (s) => {
    if (!isFinite(s)) return '0:00';
    s = Math.floor(s);
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${r.toString().padStart(2, '0')}`;
  };

  const setPlaying = (p) => {
    iconPlay.style.display = p ? 'none' : '';
    iconPause.style.display = p ? '' : 'none';
    if ('mediaSession' in navigator) {
      navigator.mediaSession.playbackState = p ? 'playing' : 'paused';
    }
  };

  const skipBy = (d) => {
    audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + d));
  };

  // ---- 播放控制 ----
  btnPlay.addEventListener('click', () => {
    if (audio.paused) audio.play().catch(() => {}); else audio.pause();
  });
  audio.addEventListener('play', () => setPlaying(true));
  audio.addEventListener('pause', () => setPlaying(false));
  audio.addEventListener('ended', () => setPlaying(false));

  audio.addEventListener('loadedmetadata', () => {
    tDur.textContent = fmt(audio.duration);
    updateMediaPosition();
  });

  audio.addEventListener('timeupdate', () => {
    const pct = audio.duration ? (audio.currentTime / audio.duration) * 100 : 0;
    fill.style.width = pct + '%';
    thumb.style.left = pct + '%';
    tNow.textContent = fmt(audio.currentTime);
    updateMediaPosition();
  });

  // ---- 进度条 (支持触屏拖动) ----
  let scrubbing = false;
  const seekFromEvent = (e) => {
    const r = bar.getBoundingClientRect();
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
    const pct = Math.max(0, Math.min(1, x / r.width));
    if (audio.duration) audio.currentTime = pct * audio.duration;
  };
  bar.addEventListener('click', seekFromEvent);
  bar.addEventListener('touchstart', (e) => { scrubbing = true; seekFromEvent(e); }, { passive: true });
  bar.addEventListener('touchmove', (e) => { if (scrubbing) seekFromEvent(e); }, { passive: true });
  bar.addEventListener('touchend', () => { scrubbing = false; });

  btnBack && btnBack.addEventListener('click', () => skipBy(-15));
  btnFwd && btnFwd.addEventListener('click', () => skipBy(15));

  // ---- 倍速 ----
  speedBtns.forEach((b) => {
    b.addEventListener('click', () => {
      speedBtns.forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      audio.playbackRate = parseFloat(b.dataset.speed);
    });
  });

  // ---- 键盘快捷键 ----
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.code === 'Space') { e.preventDefault(); btnPlay.click(); }
    else if (e.code === 'ArrowLeft') skipBy(-5);
    else if (e.code === 'ArrowRight') skipBy(5);
  });

  // ==================================================
  // MediaSession API: 锁屏 / 控制中心 / AirPods / 车机
  // ==================================================
  if ('mediaSession' in navigator) {
    const title = root.dataset.title || document.title;
    const artist = root.dataset.artist || '';
    const album = root.dataset.album || '';
    const artwork = root.dataset.artwork || '';

    navigator.mediaSession.metadata = new MediaMetadata({
      title, artist, album,
      artwork: artwork ? [
        { src: artwork, sizes: '192x192', type: 'image/png' },
        { src: artwork, sizes: '512x512', type: 'image/png' },
        { src: artwork, sizes: '1400x1400', type: 'image/png' },
      ] : [],
    });

    navigator.mediaSession.setActionHandler('play', () => audio.play());
    navigator.mediaSession.setActionHandler('pause', () => audio.pause());
    navigator.mediaSession.setActionHandler('seekbackward', (d) => skipBy(-(d.seekOffset || 15)));
    navigator.mediaSession.setActionHandler('seekforward', (d) => skipBy(d.seekOffset || 15));
    navigator.mediaSession.setActionHandler('seekto', (d) => {
      if (d.fastSeek && 'fastSeek' in audio) { audio.fastSeek(d.seekTime); return; }
      audio.currentTime = d.seekTime;
    });
    // 锁屏的"上一首/下一首"映射到归档里相邻的期 (有的话)
    const prevEp = document.querySelector('link[rel="prev"]');
    const nextEp = document.querySelector('link[rel="next"]');
    if (prevEp) {
      navigator.mediaSession.setActionHandler('previoustrack', () => location.href = prevEp.href);
    }
    if (nextEp) {
      navigator.mediaSession.setActionHandler('nexttrack', () => location.href = nextEp.href);
    }
  }

  function updateMediaPosition() {
    if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState) return;
    if (!audio.duration || !isFinite(audio.duration)) return;
    try {
      navigator.mediaSession.setPositionState({
        duration: audio.duration,
        playbackRate: audio.playbackRate,
        position: audio.currentTime,
      });
    } catch (e) { /* iOS 偶尔抛错,忽略 */ }
  }
})();
