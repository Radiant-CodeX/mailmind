import React from "react";
import { Composition } from "remotion";
import { MailMindReveal, TOTAL_DURATION } from "./MailMindReveal";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MailMindReveal"
      component={MailMindReveal}
      durationInFrames={TOTAL_DURATION}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
