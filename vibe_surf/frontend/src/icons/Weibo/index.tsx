import React, { forwardRef } from "react";
import WeiboSVG from "./Weibo.jsx";

export const WeiboIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <WeiboSVG ref={ref} {...props} />;
});