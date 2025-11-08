import React, { forwardRef } from "react";
import SvgWeibo from "./weibo-icon.svg?react";

export const WeiboIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWeibo ref={ref} {...props} />;
});