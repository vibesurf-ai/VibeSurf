import React, { forwardRef } from "react";
import SvgWeibo from "./Weibo";

export const WeiboIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWeibo ref={ref} {...props} />;
});