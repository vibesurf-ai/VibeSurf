const WeiboSVG = (props) => {
  return props.isDark ? (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fillRule="nonzero"
      {...props}
    >
      <g
        fill="#ffffff"
        fillRule="nonzero"
        stroke="none"
        strokeWidth="1"
        strokeLinecap="butt"
        strokeLinejoin="miter"
        strokeMiterlimit="10"
        strokeDasharray=""
        strokeDashoffset="0"
        fontFamily="none"
        fontWeight="none"
        fontSize="none"
        textAnchor="none"
        style={{ mixBlendMode: "normal" }}
      >
        <path d="M8.5 14c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm0-4.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5z"/>
        <path d="M19.5 8.5c-.28 0-.5-.22-.5-.5 0-3.86-3.14-7-7-7s-7 3.14-7 7c0 .28-.22.5-.5.5s-.5-.22-.5-.5c0-4.41 3.59-8 8-8s8 3.59 8 8c0 .28-.22.5-.5.5z"/>
        <path d="M16.5 11.5c-.28 0-.5-.22-.5-.5 0-2.21-1.79-4-4-4s-4 1.79-4 4c0 .28-.22.5-.5.5s-.5-.22-.5-.5c0-2.76 2.24-5 5-5s5 2.24 5 5c0 .28-.22.5-.5.5z"/>
        <path d="M12 21c-4.97 0-9-4.03-9-9s4.03-9 9-9 9 4.03 9 9-4.03 9-9 9zm0-17c-4.41 0-8 3.59-8 8s3.59 8 8 8 8-3.59 8-8-3.59-8-8-8z"/>
      </g>
    </svg>
  ) : (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width="24px"
      height="24px"
      fill="#E6162D"
      {...props}
    >
      <path d="M8.5 14c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm0-4.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5z"/>
      <path d="M19.5 8.5c-.28 0-.5-.22-.5-.5 0-3.86-3.14-7-7-7s-7 3.14-7 7c0 .28-.22.5-.5.5s-.5-.22-.5-.5c0-4.41 3.59-8 8-8s8 3.59 8 8c0 .28-.22.5-.5.5z"/>
      <path d="M16.5 11.5c-.28 0-.5-.22-.5-.5 0-2.21-1.79-4-4-4s-4 1.79-4 4c0 .28-.22.5-.5.5s-.5-.22-.5-.5c0-2.76 2.24-5 5-5s5 2.24 5 5c0 .28-.22.5-.5.5z"/>
      <path d="M12 21c-4.97 0-9-4.03-9-9s4.03-9 9-9 9 4.03 9 9-4.03 9-9 9zm0-17c-4.41 0-8 3.59-8 8s3.59 8 8 8 8-3.59 8-8-3.59-8-8-8z"/>
    </svg>
  );
};

export default WeiboSVG;