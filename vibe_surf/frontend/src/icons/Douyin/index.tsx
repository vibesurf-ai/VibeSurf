import React, { forwardRef } from "react";
import DouyinSVG from "./Douyin.jsx";

export const DouyinIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DouyinSVG ref={ref} {...props} />;
});