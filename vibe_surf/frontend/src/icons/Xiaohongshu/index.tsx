import React, { forwardRef } from "react";
import XiaohongshuSVG from "./Xiaohongshu.jsx";

export const XiaohongshuIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <XiaohongshuSVG ref={ref} {...props} />;
});