import { useParams } from "react-router-dom";

export function AdminSessionDetailPage() {
  const { sessionId } = useParams();

  return (
    <section className="content-block">
      <p className="section-label">/admin/sessions/:sessionId</p>
      <h2>세션 상세</h2>
      <p className="content-copy">
        대화 로그, 최신 분석 카드, 실패 상태, 운영 메모가 들어갈 자리입니다.
      </p>
      <p className="content-meta">예시 sessionId: {sessionId}</p>
    </section>
  );
}
