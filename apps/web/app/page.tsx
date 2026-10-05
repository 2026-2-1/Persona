"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, screenshotUrl } from "@/lib/api";
import { isActive, type Health, type SessionDetail, type SessionStatus, type SessionSummary } from "@/lib/types";

const statusLabels: Record<SessionStatus, string> = {
  queued: "실행 대기",
  running: "실행 중",
  succeeded: "실행 완료",
  technical_error: "실행 오류",
  cancelled: "중단됨",
};

function formatTime(value: string | null, includeDate = false): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    ...(includeDate ? { month: "2-digit", day: "2-digit" } as const : {}),
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function Status({ status }: { status: SessionStatus }) {
  return <span className={`status status-${status}`}><span className="status-dot" />{statusLabels[status]}</span>;
}

function Screenshot({ path, label }: { path: string | null; label: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <figure className="screenshot">
      <figcaption>{label}</figcaption>
      {path ? (
        <a href={screenshotUrl(path)} target="_blank" rel="noopener noreferrer" aria-label={`${label} 화면 원본 열기`}>
          {failed ? <span className="image-empty">미리보기를 불러오지 못했습니다. 원본 화면 열기</span> : (
            // Browser evidence is served by the local API, without image optimization.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={screenshotUrl(path)} alt={`${label} 브라우저 화면`} loading="lazy" onError={() => setFailed(true)} />
          )}
        </a>
      ) : <div className="image-empty">아직 저장된 화면이 없습니다.</div>}
    </figure>
  );
}

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [listLoaded, setListLoaded] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);
  const [detailError, setDetailError] = useState<{ id: string; message: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(true);
  const overviewVersion = useRef(0);
  const detailVersion = useRef(0);
  const selectedIdRef = useRef<string | null>(null);
  const needsOverviewPolling = useRef(true);
  const createPending = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const selectSession = useCallback((id: string) => {
    selectedIdRef.current = id;
    setSelectedId(id);
    setDetailRefreshKey((current) => current + 1);
  }, []);

  const loadOverview = useCallback(async () => {
    const version = ++overviewVersion.current;
    const [healthResult, listResult] = await Promise.allSettled([api.health(), api.sessions()]);
    if (!mounted.current || version !== overviewVersion.current) return;
    if (healthResult.status === "fulfilled") {
      setHealth(healthResult.value);
      setHealthError(null);
    } else {
      setHealth(null);
      setHealthError(errorMessage(healthResult.reason));
    }
    if (listResult.status === "fulfilled") {
      const newestFirst = [...listResult.value].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
      setSessions(newestFirst);
      setListLoaded(true);
      setListError(null);
      if (!selectedIdRef.current && newestFirst.length) selectSession(newestFirst[0].id);
      needsOverviewPolling.current = healthResult.status === "rejected" || newestFirst.some((session) => isActive(session.status));
    } else {
      setListError(errorMessage(listResult.reason));
      needsOverviewPolling.current = true;
    }
    setRefreshing(false);
  }, [selectSession]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadOverview(), 0);
    const timer = window.setInterval(() => {
      if (needsOverviewPolling.current) void loadOverview();
    }, 2000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
      overviewVersion.current += 1;
    };
  }, [loadOverview]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let stopped = false;
    const poll = async () => {
      let keepPolling = true;
      const version = detailVersion.current;
      try {
        const result = await api.session(selectedId, controller.signal);
        if (stopped || selectedIdRef.current !== selectedId || version !== detailVersion.current) return;
        setDetail(result);
        setDetailError(null);
        setSessions((current) => current.map((item) => item.id === result.id ? result : item));
        keepPolling = isActive(result.status);
      } catch (error) {
        if (stopped || selectedIdRef.current !== selectedId) return;
        setDetailError({ id: selectedId, message: errorMessage(error) });
      }
      if (!stopped && keepPolling) timer = window.setTimeout(() => void poll(), 2000);
    };
    void poll();
    return () => {
      stopped = true;
      controller.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [selectedId, detailRefreshKey]);

  async function createSession() {
    if (createPending.current) return;
    createPending.current = true;
    setCreating(true);
    setActionError(null);
    try {
      const result = await api.createSession(crypto.randomUUID());
      if (!mounted.current) return;
      overviewVersion.current += 1;
      setSessions((current) => [result, ...current.filter((item) => item.id !== result.id)]);
      setListLoaded(true);
      needsOverviewPolling.current = true;
      selectSession(result.id);
      setDetail(result);
      setRefreshing(true);
      await loadOverview();
    } catch (error) {
      if (mounted.current) {
        setActionError(errorMessage(error));
        void loadOverview();
      }
    } finally {
      createPending.current = false;
      if (mounted.current) setCreating(false);
    }
  }

  async function cancelSession(id: string) {
    setCancellingId(id);
    setActionError(null);
    try {
      const result = await api.cancelSession(id);
      if (!mounted.current) return;
      if (selectedIdRef.current === id) {
        detailVersion.current += 1;
        setDetail(result);
        setDetailRefreshKey((current) => current + 1);
      }
      setSessions((current) => current.map((item) => item.id === id ? result : item));
      setRefreshing(true);
      await loadOverview();
    } catch (error) {
      if (mounted.current) setActionError(errorMessage(error));
    } finally {
      if (mounted.current) setCancellingId(null);
    }
  }

  const selected = detail?.id === selectedId ? detail : null;
  const selectedError = detailError?.id === selectedId ? detailError.message : null;

  return (
    <main className="workbench">
      <header className="masthead">
        <div className="brand"><span className="brand-mark" aria-hidden="true">p</span><span>Persona</span></div>
        <p className="masthead-note">페르소나 실행 작업실</p>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <div>
          <h1 id="page-title">행동을 실행하고,<br />화면으로 확인하세요.</h1>
          <p>페르소나가 과업을 수행한 과정과 각 단계의 화면을 확인합니다.</p>
        </div>
        <div className={`connection ${health ? "connected" : ""}`} aria-live="polite">
          <span className="connection-dot" aria-hidden="true" />
          <div><strong>{health ? "서버 연결됨" : healthError ? "서버 연결 필요" : "연결 확인 중"}</strong>
            <span>{health ? health.model_provider === "mock" ? "샘플 응답으로 실행합니다" : `모델: ${health.model_provider}` : "실행 서버의 상태를 확인합니다"}</span>
          </div>
        </div>
      </section>

      {healthError && <div className="notice error-notice" role="status">{healthError}</div>}

      <section className="task-launch" aria-labelledby="task-title">
        <div className="task-index">T02</div>
        <div className="task-description"><h2 id="task-title">상품 정보 확인 <span>초보 러너</span></h2>
          <p>로컬 샘플 상품의 가격·사이즈·용도를 확인합니다.</p>
        </div>
        <button className="primary-button" onClick={() => void createSession()} disabled={creating || !health}>
          {creating ? "실행 요청 중…" : "샘플 과업 실행"}
        </button>
      </section>
      {actionError && <div className="notice error-notice" role="alert">{actionError}</div>}

      <div className="panels">
        <section className="session-panel" aria-labelledby="sessions-title">
          <div className="panel-heading"><div><h2 id="sessions-title">실행 기록</h2><p>최신 기록부터 표시합니다</p></div>
            <button className="text-button" onClick={() => { setRefreshing(true); setDetailRefreshKey((current) => current + 1); void loadOverview(); }} disabled={refreshing} aria-label="서버 상태와 실행 기록 새로고침">{refreshing ? "확인 중…" : "새로고침"}</button>
          </div>
          {listError && <div className="notice error-notice compact" role="status">{listError}</div>}
          {sessions.length ? (
            <ul className="session-list">
              {sessions.map((session) => (
                <li key={session.id}><button className={`session-row ${session.id === selectedId ? "selected" : ""}`} onClick={() => selectSession(session.id)} aria-pressed={session.id === selectedId}>
                  <span className="row-top"><strong>{session.persona_name}</strong><Status status={session.status} /></span>
                  <span className="row-task">{session.task_id} 상품 정보 확인</span>
                  <span className="row-bottom"><time dateTime={session.created_at}>{formatTime(session.created_at, true)}</time><span>{session.id.slice(0, 8)}</span></span>
                </button></li>
              ))}
            </ul>
          ) : <div className="empty-state small"><div className="empty-lane" aria-hidden="true" /><h3>{listLoaded ? "첫 실행을 시작하세요" : listError ? "기록을 가져오지 못했습니다" : "실행 기록을 불러오는 중"}</h3><p>{listLoaded ? "샘플 과업을 실행하면 이곳에 기록이 쌓입니다." : listError ? "서버 연결을 확인하고 새로고침해 주세요." : "잠시만 기다려 주세요."}</p></div>}
        </section>

        <section className="evidence-panel" aria-labelledby="evidence-title">
          <div className="panel-heading"><div><h2 id="evidence-title">실행 과정</h2><p>단계별 행동과 전후 화면</p></div>
            {selected && isActive(selected.status) && <button className="stop-button" onClick={() => void cancelSession(selected.id)} disabled={cancellingId !== null}>{cancellingId === selected.id ? "중단 요청 중…" : "실행 중단"}</button>}
          </div>
          {selectedError && <div className="notice error-notice compact" role="status">{selectedError}</div>}
          {selected ? (
            <>
              <div className="session-summary"><div className="summary-title"><h3>{selected.persona_name}</h3><Status status={selected.status} /></div>
                <dl className="summary-times"><div><dt>요청</dt><dd>{formatTime(selected.created_at)}</dd></div><div><dt>시작</dt><dd>{formatTime(selected.started_at)}</dd></div><div><dt>종료</dt><dd>{formatTime(selected.finished_at)}</dd></div></dl>
                {selected.error && <p className="session-error">{selected.error}</p>}
              </div>
              {selected.steps.length ? <ol className="step-list">{[...selected.steps].sort((a, b) => a.step_no - b.step_no).map((step) => (
                <li className="step" key={step.id}>
                  <div className="step-heading"><span className="step-number">{step.step_no}</span><div><h4>{step.description || step.action}</h4><p><span>{step.action}</span><time dateTime={step.created_at}>{formatTime(step.created_at)}</time><span>{step.status === "succeeded" ? "완료" : step.status === "technical_error" ? "오류" : step.status}</span></p></div></div>
                  <p className="step-url" title={step.url}>{step.url}</p>
                  <div className="screenshots"><Screenshot key={`${step.id}-before-${step.screenshot_before}`} path={step.screenshot_before} label="행동 전" /><Screenshot key={`${step.id}-after-${step.screenshot_after}`} path={step.screenshot_after} label="행동 후" /></div>
                </li>
              ))}</ol> : <div className="empty-state"><div className="empty-lane" aria-hidden="true" /><h3>{isActive(selected.status) ? "행동 기록을 기다리는 중" : "저장된 행동 기록이 없습니다"}</h3><p>{isActive(selected.status) ? "실행 과정은 자동으로 갱신됩니다." : "실행 상태와 오류 내용을 확인해 주세요."}</p></div>}
            </>
          ) : <div className="empty-state"><div className="empty-lane" aria-hidden="true" /><h3>{selectedId ? "실행 과정을 불러오는 중" : "확인할 실행을 선택하세요"}</h3><p>{selectedId ? "서버에서 단계별 기록을 가져옵니다." : "왼쪽 기록을 선택하거나 샘플 과업을 실행해 주세요."}</p></div>}
        </section>
      </div>

      <footer className="page-footer"><span>화면 기록은 원본 크기로 열어 확인할 수 있습니다.</span><span>로컬 샘플 과업</span></footer>
    </main>
  );
}
