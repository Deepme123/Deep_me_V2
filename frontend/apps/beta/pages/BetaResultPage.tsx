import { useParams } from "react-router-dom";

export function BetaResultPage() {
  const { sessionId } = useParams();

  return (
    <section className="content-block">
      <p className="section-label">/beta/result/:sessionId</p>
      <h2>베타 결과 화면</h2>
      <p className="content-copy">
        세션 종료 후 분석 카드와 요약 결과를 표시할 자리입니다.
      </p>
      <p className="content-meta">예시 sessionId: {sessionId}</p>
    </section>
  );
}
